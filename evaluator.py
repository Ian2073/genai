import json
import logging
import re
import math
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Set, Any, Tuple
from collections import defaultdict
import random
import statistics

from runtime.compat import prepare_evaluator_runtime

logging.basicConfig(level=logging.INFO, format='System: %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CharacterCluster:
    cluster_id: int
    mentions: List[str]
    mention_spans: List[Any] # spacy spans/tokens
    canonical_name: str

@dataclass
class CharacterState:
    name_variants: Set[str]
    attributes_by_type: Dict[str, Set[str]]
    pronoun_mentions: int

@dataclass
class CharacterProfile:
    canonical_name: str
    name_variants: List[str]
    attributes_by_type: Dict[str, List[str]]
    occurrence_positions: List[int]

@dataclass
class NameConflict:
    character_id: str
    conflicting_names: List[str]
    severity: int = 3

@dataclass
class AttributeConflict:
    character_id: str
    attribute_type: str
    conflicting_values: List[str]
    severity: int = 2

@dataclass
class CorefConflict:
    pronoun: str
    sentence: str
    candidate_count: int
    severity: int = 1

@dataclass
class ConsistencyMetrics:
    name_conflict_count: int = 0
    attribute_conflict_count: int = 0
    coref_error_count: int = 0
    total_conflicts: int = 0
    severity_sum: int = 0
    has_error: int = 0
    total_words: int = 0
    total_tokens: int = 0
    conflict_details: List[Dict[str, Any]] = field(default_factory=list)
    complexity: Dict[str, Any] = field(default_factory=dict)
    structure: Dict[str, Any] = field(default_factory=dict)


MUTUALLY_EXCLUSIVE_ATTRIBUTES = [
    {"boy", "girl", "man", "woman", "gentleman", "lady", "male", "female"},
    {"young", "old", "elderly", "youthful", "child", "adult", "baby", "teenager"},
    {"tall", "short", "giant", "tiny"},
    {"king", "queen", "prince", "princess", "peasant", "villager", "commoner"},
    {"hero", "villain", "monster", "human"},
    {"blonde", "brunette", "redhead", "bald"},
]

class ConsistencyEvaluator:
    def __init__(
        self,
        model_name: str = "en_core_web_sm",
        coref_model: str = "en_coreference_web_trf",
        enable_attribute_conflicts: bool = False,
        late_intro_max_mentions: int = 2,
        include_structure_metrics_in_stats: bool = False,
    ):
        """
        Initializes the ConsistencyEvaluator. 
        """
        import spacy
        
        # 將第三方相容修補集中在 `runtime/compat.py`，方便維護與教學說明。
        prepare_evaluator_runtime()

        self.nlp = None
        self.coref_nlp = None
        self.has_coref = False
        self.enable_attribute_conflicts = bool(enable_attribute_conflicts)
        self.late_intro_max_mentions = max(1, int(late_intro_max_mentions))
        self.include_structure_metrics_in_stats = bool(include_structure_metrics_in_stats)
        try:
            self.nlp = spacy.load(model_name)
            logger.info("Loaded spaCy pipeline: %s", model_name)
        except Exception as e:
            logger.warning(f"Failed to load spacy model or dependency: {e}")
            logger.warning("Will proceed with lightweight heuristic parsing.")
            self.nlp = spacy.blank("en")
            if "sentencizer" not in self.nlp.pipe_names:
                self.nlp.add_pipe("sentencizer")

        try:
            self.coref_nlp = spacy.load(coref_model)
            self.has_coref = True
            logger.info("Successfully loaded experimental coreference resolution (Parallel Pipeline).")
        except Exception as e:
            logger.warning("Failed to load coreference model or dependency: %s", e)
            logger.warning("Coreference metrics will use heuristic fallback only.")
            self.coref_nlp = None
            self.has_coref = False

        # 角色一致性評估只關注人物代名詞，不納入物件指代 (it/its)。
        self.PRONOUNS_3RD = {"he", "him", "his", "she", "her", "hers", "they", "them", "their", "theirs"}
        if not self.enable_attribute_conflicts:
            logger.info("Attribute conflict detection is disabled (default).")
        if not self.include_structure_metrics_in_stats:
            logger.info("Structure metrics are exported but excluded from permutation stats (default).")

    def _normalize_person_name(self, text: str) -> str:
        """將人物稱呼做穩健正規化，降低 token/所有格造成的假衝突。"""
        if not text:
            return ""
        value = str(text)
        value = value.replace("\u2019", "'").replace("\u2018", "'")
        value = value.replace("\uFFFD", "")
        value = re.sub(r"\s+", " ", value).strip(" \t\n\r.,;:!?\"()[]{}")

        # 去掉尾端所有格與孤立撇號：Emma's / Emma' / Grandpa Tom'
        value = re.sub(r"(?i)(?:'s|')$", "", value).strip()

        # 去掉尾端常見代詞/限定詞殘片：Grandpa Tom their
        value = re.sub(r"(?i)\s+(their|theirs|his|her|hers|him|them)$", "", value).strip()

        # 移除前綴冠詞，避免 "the Emma" 類殘片
        value = re.sub(r"(?i)^(the|a|an)\s+", "", value).strip()

        # 把多餘符號再清一次
        value = re.sub(r"[^A-Za-z\-\s.]", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def _is_person_like_span(self, span) -> bool:
        """判斷 mention 是否具有人物名稱特徵。"""
        if span is None:
            return False
        for token in span:
            if token.pos_ == "PROPN" or token.ent_type_ == "PERSON":
                return True
        return False

    def _is_title_case_name(self, text: str) -> bool:
        """判斷文字是否像人名（Title Case 多詞）。"""
        if not text:
            return False
        tokens = [t for t in text.split() if t]
        if not tokens:
            return False
        good = 0
        for token in tokens:
            if re.match(r"^[A-Z][a-z\-]*$", token):
                good += 1
        return good >= 1

    def evaluate(self, story_text: str, story_id: str = "default_story") -> str:
        """
        Main pipeline function:
        text -> character state reconstruction -> conflict detection -> numeric report
        """
        doc = self._preprocess(story_text)
        coref_doc = self.coref_nlp(story_text) if self.has_coref else None
        
        clusters = self._extract_entities_and_coref(doc, coref_doc)
        char_states = self._extract_attributes(doc, clusters)
        profiles = self._construct_character_profiles(clusters, char_states)
        conflicts = self._detect_conflicts(doc, profiles)
        metrics = self._score_severity(conflicts)
        metrics.complexity = self._compute_complexity_metrics(doc)
        metrics.structure = self._compute_structure_metrics(doc, profiles)
        
        # Calculate text length metrics
        metrics.total_tokens = len(doc)
        metrics.total_words = len([token for token in doc if not token.is_punct and not token.is_space])
        
        return self._generate_report(story_id, metrics)

    def _compute_structure_metrics(self, doc, profiles: Dict[int, CharacterProfile]) -> Dict[str, Any]:
        """計算可客觀自動化的結構一致性輔助指標。"""
        sentences = list(doc.sents)
        sentence_count = len(sentences)

        if not profiles:
            return {
                "distinct_name_forms_total": 0,
                "characters_with_multiple_name_forms": 0,
                "late_introduced_characters": 0,
                "main_character_drop_count": 0,
                "character_set_drift_mean": 0.0,
            }

        # A) 名稱變體：不看衝突，只看同角色的稱呼形式數
        distinct_name_forms_total = 0
        characters_with_multiple_name_forms = 0
        profile_name_forms: Dict[int, Set[str]] = {}
        for c_id, profile in profiles.items():
            forms: Set[str] = set()
            canonical = self._normalize_person_name(profile.canonical_name)
            if canonical and self._is_title_case_name(canonical):
                forms.add(canonical.lower())
            for variant in profile.name_variants:
                normalized = self._normalize_person_name(variant)
                if normalized and self._is_title_case_name(normalized):
                    forms.add(normalized.lower())
            if not forms and canonical:
                forms.add(canonical.lower())
            profile_name_forms[c_id] = forms
            distinct_name_forms_total += len(forms)
            if len(forms) > 1:
                characters_with_multiple_name_forms += 1

        # B) 角色晚出：首次出現落在最後 1/3 且提及次數 <= 門檻（多為突然引入）
        late_boundary = int(sentence_count * (2 / 3)) if sentence_count > 0 else 0
        late_introduced_characters = 0

        # 先建立每句有哪些角色，方便 C/D 指標共用
        sentence_character_sets: List[Set[int]] = []
        for sent in sentences:
            present: Set[int] = set()
            s_start, s_end = sent.start, sent.end
            for c_id, profile in profiles.items():
                for pos in profile.occurrence_positions:
                    if s_start <= pos < s_end:
                        present.add(c_id)
                        break
            sentence_character_sets.append(present)

        first_seen_sent_idx: Dict[int, int] = {}
        for idx, cset in enumerate(sentence_character_sets):
            for c_id in cset:
                if c_id not in first_seen_sent_idx:
                    first_seen_sent_idx[c_id] = idx

        mention_count_by_char = {c_id: len(profile.occurrence_positions) for c_id, profile in profiles.items()}
        for c_id, first_idx in first_seen_sent_idx.items():
            if first_idx >= late_boundary and mention_count_by_char.get(c_id, 0) <= self.late_intro_max_mentions:
                late_introduced_characters += 1

        # C) 主角消失：前兩高頻角色若在最後 1/3 完全缺席，記為 drop
        sorted_chars = sorted(mention_count_by_char.items(), key=lambda x: x[1], reverse=True)
        main_character_ids = [cid for cid, _ in sorted_chars[:2]]
        final_segment_start = late_boundary
        final_chars: Set[int] = set()
        for idx in range(final_segment_start, sentence_count):
            final_chars.update(sentence_character_sets[idx])
        main_character_drop_count = sum(1 for cid in main_character_ids if cid not in final_chars)

        # D) 角色集合漂移：三段相鄰區塊角色集合 Jaccard drift 平均值
        if sentence_count == 0:
            character_set_drift_mean = 0.0
        else:
            segment_count = 3
            chunk_size = max(1, math.ceil(sentence_count / segment_count))
            segment_sets: List[Set[int]] = []
            for i in range(0, sentence_count, chunk_size):
                merged: Set[int] = set()
                for cset in sentence_character_sets[i:i + chunk_size]:
                    merged.update(cset)
                segment_sets.append(merged)

            drifts: List[float] = []
            for i in range(len(segment_sets) - 1):
                left = segment_sets[i]
                right = segment_sets[i + 1]
                union = left.union(right)
                if not union:
                    drifts.append(0.0)
                    continue
                jaccard = len(left.intersection(right)) / len(union)
                drifts.append(1.0 - jaccard)
            character_set_drift_mean = round(statistics.mean(drifts), 4) if drifts else 0.0

        return {
            "distinct_name_forms_total": distinct_name_forms_total,
            "characters_with_multiple_name_forms": characters_with_multiple_name_forms,
            "late_introduced_characters": late_introduced_characters,
            "main_character_drop_count": main_character_drop_count,
            "character_set_drift_mean": character_set_drift_mean,
        }

    def _preprocess(self, text: str):
        return self.nlp(text)

    def _extract_entities_and_coref(self, doc, coref_doc=None) -> Dict[int, CharacterCluster]:
        clusters_map = {}
        
        # EXPERIMENTAL COREF RESOLUTION
        if self.has_coref and coref_doc is not None and len(coref_doc.spans) > 0:
            logger.info("Extracting coreferences via spacy-experimental transformers.")
            # spacy-experimental stores clusters in doc.spans
            # e.g doc.spans["coref_clusters_1"], doc.spans["coref_clusters_2"]...
            
            cluster_id_counter = 0
            for cluster_key in coref_doc.spans:
                if not cluster_key.startswith("coref_clusters_"):
                    continue
                
                spans = coref_doc.spans[cluster_key]
                if not spans: continue
                
                mentions = []
                mention_spans = []
                anchor_names = []
                
                for coref_span in spans:
                    mention_text = coref_span.text
                    mentions.append(mention_text)
                    
                    # Align the span from coref_doc back to doc (same tokenizer)
                    span = doc[coref_span.start : coref_span.end]
                    mention_spans.append(span)
                    
                    if self._is_person_like_span(span):
                        normalized = self._normalize_person_name(mention_text)
                        if normalized:
                            anchor_names.append(normalized)
                
                # Only register clusters that actually map to a named entity or clear noun
                if anchor_names:
                    canonical_name = max(set(anchor_names), key=len)
                    clusters_map[cluster_id_counter] = CharacterCluster(
                        cluster_id=cluster_id_counter,
                        mentions=mentions,
                        mention_spans=mention_spans,
                        canonical_name=canonical_name
                    )
                    cluster_id_counter += 1
            return clusters_map

        # FALLBACK APPROACH (Pure Python Heuristic)
        logger.info("Using smart heuristic entity extraction.")
        cluster_idx = 0
            
        # 1. Identify character names from PERSON entities
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                name = ent.text.strip()
                found = False
                for c_id, c_data in clusters_map.items():
                    if name in c_data.canonical_name or c_data.canonical_name in name:
                        found = True
                        break
                if not found:
                    clusters_map[cluster_idx] = CharacterCluster(
                        cluster_id=cluster_idx,
                        mentions=[],
                        mention_spans=[],
                        canonical_name=name
                    )
                    cluster_idx += 1
                    
        # 2. Find all occurrences of these names
        for c_id, c_data in clusters_map.items():
            name_lower = c_data.canonical_name.lower()
            for token in doc:
                if token.text.lower() == name_lower:
                    span = doc[token.i:token.i+1]
                    c_data.mentions.append(token.text)
                    c_data.mention_spans.append(span)

        # 3. Very basic pronoun resolution heuristic targeting long texts
        # Instead of penalizing all pronouns without nearby names, we just map 
        # strong subject pronouns (he, she, they) to the most recently mentioned character.
        # This prevents false-positive explosions on long paragraphs.
        last_seen_character_id = None
        for i, token in enumerate(doc):
            if token.pos_ in ("PROPN", "NOUN"):
                for c_id, c_data in clusters_map.items():
                    if token.text in c_data.canonical_name:
                        last_seen_character_id = c_id
                        break
            
            if token.pos_ == "PRON" and token.dep_ == "nsubj":
                pronoun_text = token.text.lower()
                if pronoun_text in ("he", "she", "they") and last_seen_character_id is not None:
                    span = doc[token.i : token.i + 1]
                    clusters_map[last_seen_character_id].mentions.append(token.text)
                    clusters_map[last_seen_character_id].mention_spans.append(span)

        return clusters_map

    def _extract_attributes(self, doc, clusters: Dict[int, CharacterCluster]) -> Dict[int, CharacterState]:
        states = {}
        for c_id, cluster in clusters.items():
            name_variants = set()
            attributes = set()
            pronoun_count = 0
            
            for span in cluster.mention_spans:
                text_lower = span.text.lower()
                if text_lower in self.PRONOUNS_3RD:
                    pronoun_count += 1
                else:
                    if self._is_person_like_span(span):
                        normalized = self._normalize_person_name(span.text)
                        if normalized and self._is_title_case_name(normalized):
                            name_variants.add(normalized)
                
                # Attribute extraction via dependency parsing
                root = span.root
                
                # amod modifier: "The short Alice"
                for child in root.children:
                    if child.dep_ == "amod" and child.pos_ == "ADJ":
                        attributes.add(child.text.lower())
                
                # acomp and attr: "Alice is tall", "Alice is a tall girl"
                if root.dep_ in ("nsubj", "nsubjpass"):
                    head = root.head
                    if head.pos_ in ("AUX", "VERB"):
                        for child in head.children:
                            # acomp
                            if child.dep_ == "acomp" and child.pos_ == "ADJ":
                                attributes.add(child.text.lower())
                            # attr ("girl" in "Alice is a very tall girl")
                            if child.dep_ == "attr":
                                # 直接擷取名詞屬性（例如 prince/villager）
                                attr_text = child.text.lower()
                                if any(attr_text in ex for ex in MUTUALLY_EXCLUSIVE_ATTRIBUTES):
                                    attributes.add(attr_text)
                                for grandchild in child.children:
                                    if grandchild.dep_ == "amod" and grandchild.pos_ == "ADJ":
                                        attributes.add(grandchild.text.lower())

            attributes_by_type = defaultdict(set)
            for attr in attributes:
                found = False
                for idx, exclusive_set in enumerate(MUTUALLY_EXCLUSIVE_ATTRIBUTES):
                    if attr in exclusive_set:
                        attributes_by_type[f"trait_group_{idx}"].add(attr)
                        found = True
                        break
                if not found:
                    attributes_by_type["other"].add(attr)

            states[c_id] = CharacterState(
                name_variants=name_variants,
                attributes_by_type=dict(attributes_by_type),
                pronoun_mentions=pronoun_count
            )
        return states

    def _construct_character_profiles(self, clusters: Dict[int, CharacterCluster], char_states: Dict[int, CharacterState]) -> Dict[int, CharacterProfile]:
        profiles = {}
        for c_id, cluster in clusters.items():
            state = char_states[c_id]
            # Gather ALL token indices within each mention span so pronouns and multi-word names are fully covered
            positions = []
            for span in cluster.mention_spans:
                for token in span:
                    positions.append(token.i)

            profiles[c_id] = CharacterProfile(
                canonical_name=cluster.canonical_name,
                name_variants=list(state.name_variants),
                attributes_by_type={k: list(v) for k, v in state.attributes_by_type.items()},
                occurrence_positions=positions
            )
        return profiles

    def _context_candidate_count(
        self,
        token_index: int,
        profiles: Dict[int, CharacterProfile],
        lookback: int = 48,
    ) -> int:
        """估算代名詞在局部上下文中可能對應的角色數。"""
        left = max(0, token_index - lookback)
        right = token_index
        candidates = 0
        for profile in profiles.values():
            found = False
            for pos in profile.occurrence_positions:
                if left <= pos <= right:
                    found = True
                    break
            if found:
                candidates += 1
        return candidates

    def _is_contextually_resolved_pronoun(
        self,
        doc,
        token,
        cluster_spans_set: Set[int],
        profiles: Dict[int, CharacterProfile],
    ) -> Tuple[bool, int]:
        """以語境可解析性判斷代名詞是否應視為衝突。"""
        if token.i in cluster_spans_set:
            return True, 1

        pron = token.text.lower()
        if pron not in self.PRONOUNS_3RD:
            return True, 0

        candidate_count = self._context_candidate_count(token.i, profiles)
        plural_pronouns = {"they", "them", "their", "theirs"}

        # 規則 1：同句內若代名詞前只有單一人物專名，視為可解析
        sent = token.sent
        prior_name_count = 0
        sent_name_count = 0
        for t in sent:
            if t.pos_ == "PROPN" or t.ent_type_ == "PERSON":
                sent_name_count += 1
        for t in sent:
            if t.i >= token.i:
                break
            if t.pos_ == "PROPN" or t.ent_type_ == "PERSON":
                prior_name_count += 1

        if prior_name_count == 1:
            return True, max(candidate_count, 1)
        if prior_name_count >= 2:
            # 同句內多角色時，單數代名詞高度歧義
            if pron in {"he", "she", "him", "his", "her", "hers"}:
                return False, max(candidate_count, prior_name_count)
            # 複數代名詞對應多角色群體可解析
            if pron in plural_pronouns:
                return True, max(candidate_count, prior_name_count)

        # 規則 1b：句內後置合取主語（例如 "With their ..., Emma and Alex ..."）
        if pron in plural_pronouns and sent_name_count >= 2:
            return True, max(candidate_count, 2)

        # 規則 2：句首代名詞且前一句有人名時，視為可解析（跨句延續）
        sent_tokens = [t for t in sent if not t.is_space]
        if sent_tokens and sent_tokens[0].i == token.i:
            prev_sent_start = max(0, sent.start - 40)
            prev_name_hits = 0
            for t in doc[prev_sent_start:sent.start]:
                if t.pos_ == "PROPN" or t.ent_type_ == "PERSON":
                    prev_name_hits += 1
            if prev_name_hits == 1:
                return True, max(candidate_count, 1)
            if pron in plural_pronouns and prev_name_hits >= 1:
                return True, max(candidate_count, prev_name_hits)

        # 規則 3：對話歸屬句型（"..." he said）在有上下文人物時不直接記錯
        next_token = doc[token.i + 1] if token.i + 1 < len(doc) else None
        reporting_verbs = {
            "said", "asked", "replied", "whispered", "murmured", "shouted",
            "called", "yelled", "cried", "explained", "laughed", "gasped",
            "sighed", "added", "answered", "warned", "muttered", "cheered",
        }
        if next_token is not None and next_token.lemma_.lower() in reporting_verbs and candidate_count == 1:
            return True, candidate_count

        # 校準後判定：單數代名詞需要唯一候選，複數至少要有候選
        singular_pronouns = {"he", "she", "him", "his", "her", "hers"}
        if pron in singular_pronouns and candidate_count != 1:
            return False, candidate_count
        if pron in plural_pronouns and candidate_count == 0:
            return False, 0
        return True, candidate_count

    def _detect_conflicts(self, doc, profiles: Dict[int, CharacterProfile]) -> List[Any]:
        conflicts = []
        cluster_spans_set = set()
        
        for c_id, profile in profiles.items():
            for pos in profile.occurrence_positions:
                cluster_spans_set.add(pos)
                
            # 1. Name Conflict Detection
            # Only consider proper nouns for name conflicts to avoid flagging "the captain", "Doctor", etc.
            proper_names = []
            for name in profile.name_variants:
                normalized = self._normalize_person_name(name)
                if not normalized:
                    continue
                if not self._is_title_case_name(normalized):
                    continue
                if any(t.pos_ == "PROPN" for t in self.nlp(normalized)):
                    proper_names.append(normalized)

            # 去重（忽略大小寫）
            dedup_map: Dict[str, str] = {}
            for n in proper_names:
                key = n.lower()
                if key not in dedup_map or len(n) > len(dedup_map[key]):
                    dedup_map[key] = n
            proper_names = list(dedup_map.values())
            
            if len(proper_names) > 1:
                base_name_tokens = [set(n.lower().split()) for n in proper_names]
                has_disjoint = False
                for i in range(len(base_name_tokens)):
                    for j in range(i+1, len(base_name_tokens)):
                        # If two proper names in the same cluster share NO common words, flag as conflict. 
                        # E.g., "John Smith" and "Mr. John" share "john", but "John" and "Sarah" do not.
                        if not base_name_tokens[i].intersection(base_name_tokens[j]):
                            has_disjoint = True
                            break
                if has_disjoint:
                    conflicts.append(NameConflict(
                        character_id=profile.canonical_name,
                        conflicting_names=proper_names
                    ))
            
            # 2. Attribute Conflict Detection (optional)
            if self.enable_attribute_conflicts:
                for trait_group, traits in profile.attributes_by_type.items():
                    if trait_group.startswith("trait_group_") and len(traits) > 1:
                        conflicts.append(AttributeConflict(
                            character_id=profile.canonical_name,
                            attribute_type=trait_group,
                            conflicting_values=traits
                        ))
        
        # 3. Coreference Errors
        # 只計「未解析的人物代名詞」，避免把語言自然度(歧義)誤判成角色一致性錯誤。
        for token in doc:
            pron = token.text.lower()
            if pron not in self.PRONOUNS_3RD:
                continue

            resolved, candidate_count = self._is_contextually_resolved_pronoun(
                doc,
                token,
                cluster_spans_set,
                profiles,
            )
            if not resolved:
                conflicts.append(
                    CorefConflict(
                        pronoun=token.text,
                        sentence=token.sent.text.strip(),
                        candidate_count=candidate_count,
                    )
                )

        # Filter repetitive coref conflicts for cleaner reports
        unique_conflicts = []
        seen_sents = set()
        seen_name_conflict_keys = set()
        for c in conflicts:
            if isinstance(c, CorefConflict):
                if c.sentence not in seen_sents:
                    seen_sents.add(c.sentence)
                    unique_conflicts.append(c)
            elif isinstance(c, NameConflict):
                # 避免同一組衝突名字被多個 cluster 重複計算
                normalized = [self._normalize_person_name(n).lower() for n in c.conflicting_names]
                normalized = [n for n in normalized if n]
                key = tuple(sorted(set(normalized)))
                if key and key not in seen_name_conflict_keys:
                    seen_name_conflict_keys.add(key)
                    unique_conflicts.append(c)
            else:
                unique_conflicts.append(c)

        return unique_conflicts

    def _score_severity(self, conflicts: List[Any]) -> ConsistencyMetrics:
        """
        Calculates severity purely as a weighted auxiliary indicator to differentiate between
        minor lexical mismatches and structural character breakage. This is NOT a definitive quality score,
        but a continuous variable for statistical testing (e.g., ANOVA) in academic evaluation.
        """
        metrics = ConsistencyMetrics()
        
        for conflict in conflicts:
            metrics.total_conflicts += 1
            metrics.severity_sum += conflict.severity
            
            if isinstance(conflict, NameConflict):
                metrics.name_conflict_count += 1
                metrics.conflict_details.append({"type": "NameConflict", "details": asdict(conflict)})
            elif isinstance(conflict, AttributeConflict):
                metrics.attribute_conflict_count += 1
                metrics.conflict_details.append({"type": "AttributeConflict", "details": asdict(conflict)})
            elif isinstance(conflict, CorefConflict):
                metrics.coref_error_count += 1
                metrics.conflict_details.append({"type": "CorefConflict", "details": asdict(conflict)})
        
        if metrics.total_conflicts > 0:
            metrics.has_error = 1
            
        return metrics

    def _compute_complexity_metrics(self, doc) -> dict:
        """計算文本複雜度指標作為控制變項。"""
        import re as _re
        unique_names: set = set()
        entity_mentions = 0
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                unique_names.add(ent.text.strip())
                entity_mentions += 1
        sentences = list(doc.sents)
        pronoun_count = sum(1 for t in doc if t.text.lower() in self.PRONOUNS_3RD)
        total_words = max(1, len([t for t in doc if not t.is_space and not t.is_punct]))
        return {
            "unique_character_count": len(unique_names),
            "entity_mention_count": entity_mentions,
            "sentence_count": len(sentences),
            "pronoun_density": round(pronoun_count / total_words, 4),
        }

    def _generate_report(self, story_id: str, metrics: ConsistencyMetrics) -> str:
        total_words_safe = max(1, metrics.total_words)
        report_dict = {
            "story_id": story_id,
            "metrics": {
                "name_conflicts": metrics.name_conflict_count,
                "attribute_conflicts": metrics.attribute_conflict_count,
                "coref_errors": metrics.coref_error_count,
                "total_conflicts": metrics.total_conflicts,
                "severity_sum": metrics.severity_sum,
                "has_error": metrics.has_error,
                "total_words": metrics.total_words,
                "total_tokens": metrics.total_tokens,
                # Length-normalized metrics (Errors per 100 words)
                "name_conflicts_per_100": (metrics.name_conflict_count / total_words_safe) * 100,
                "attribute_conflicts_per_100": (metrics.attribute_conflict_count / total_words_safe) * 100,
                "coref_errors_per_100": (metrics.coref_error_count / total_words_safe) * 100,
                "total_conflicts_per_100": (metrics.total_conflicts / total_words_safe) * 100,
                # Complexity control metrics (B3)
                "unique_character_count": metrics.complexity.get("unique_character_count", 0) if hasattr(metrics, "complexity") else 0,
                "entity_mention_count": metrics.complexity.get("entity_mention_count", 0) if hasattr(metrics, "complexity") else 0,
                "sentence_count": metrics.complexity.get("sentence_count", 0) if hasattr(metrics, "complexity") else 0,
                "pronoun_density": metrics.complexity.get("pronoun_density", 0.0) if hasattr(metrics, "complexity") else 0.0,
                # Additional structure-consistency metrics
                "distinct_name_forms_total": metrics.structure.get("distinct_name_forms_total", 0),
                "characters_with_multiple_name_forms": metrics.structure.get("characters_with_multiple_name_forms", 0),
                "late_introduced_characters": metrics.structure.get("late_introduced_characters", 0),
                "main_character_drop_count": metrics.structure.get("main_character_drop_count", 0),
                "character_set_drift_mean": metrics.structure.get("character_set_drift_mean", 0.0),
                "late_introduced_characters_per_100": (metrics.structure.get("late_introduced_characters", 0) / total_words_safe) * 100,
                "main_character_drop_per_100": (metrics.structure.get("main_character_drop_count", 0) / total_words_safe) * 100,
            },
            "conflict_details": metrics.conflict_details
        }
        return json.dumps(report_dict, indent=2, ensure_ascii=False)

    def _pick_story_file(self, case_dir: Any, group: str, prefer_fair_story: bool = True) -> Any:
        """選擇評估用故事檔案。

        prefer_fair_story=True: 優先 story_for_eval，再退回 story。
        prefer_fair_story=False: 強制使用原始 story。
        """
        fallback = case_dir / group / "story.txt"
        if not prefer_fair_story:
            return fallback
        preferred = case_dir / group / "story_for_eval.txt"
        if preferred.exists():
            return preferred
        return fallback

    def _paired_sign_permutation_test(
        self,
        deltas: List[float],
        trials: int = 10000,
        seed: int = 12345,
    ) -> Dict[str, float]:
        """對配對差值做 sign-flip permutation test（可重現），並回傳分布摘要。"""
        clean_deltas: List[float] = []
        for delta in deltas:
            if isinstance(delta, (int, float)):
                clean_deltas.append(float(delta))
        if not clean_deltas:
            return {
                "n": 0,
                "observed_mean": 0.0,
                "delta_std": 0.0,
                "delta_median": 0.0,
                "delta_min": 0.0,
                "delta_max": 0.0,
                "effect_size_paired_d": 0.0,
                "p_two_sided": 1.0,
                "p_less": 1.0,
                "ci95_low": 0.0,
                "ci95_high": 0.0,
            }

        def _percentile(sorted_vals: List[float], q: float) -> float:
            if not sorted_vals:
                return 0.0
            if q <= 0:
                return sorted_vals[0]
            if q >= 1:
                return sorted_vals[-1]
            idx = (len(sorted_vals) - 1) * q
            lo = math.floor(idx)
            hi = math.ceil(idx)
            if lo == hi:
                return sorted_vals[int(idx)]
            return sorted_vals[lo] * (hi - idx) + sorted_vals[hi] * (idx - lo)

        observed_mean = statistics.mean(clean_deltas)
        delta_std = statistics.stdev(clean_deltas) if len(clean_deltas) > 1 else 0.0
        delta_median = statistics.median(clean_deltas)
        delta_min = min(clean_deltas)
        delta_max = max(clean_deltas)
        effect_size = (observed_mean / delta_std) if delta_std > 0 else 0.0
        rng = random.Random(seed)
        extreme_two_sided = 0
        extreme_less = 0
        observed_abs = abs(observed_mean)
        perm_means: List[float] = []

        for _ in range(trials):
            permuted: List[float] = []
            for value in clean_deltas:
                sign = -1.0 if rng.random() < 0.5 else 1.0
                permuted.append(sign * value)
            perm_mean = statistics.mean(permuted)
            perm_means.append(perm_mean)
            if abs(perm_mean) >= observed_abs:
                extreme_two_sided += 1
            if perm_mean <= observed_mean:
                extreme_less += 1

        # +1 correction，避免 p 值為 0
        p_two_sided = (extreme_two_sided + 1) / (trials + 1)
        p_less = (extreme_less + 1) / (trials + 1)
        perm_means.sort()
        ci95_low = _percentile(perm_means, 0.025)
        ci95_high = _percentile(perm_means, 0.975)
        return {
            "n": len(clean_deltas),
            "observed_mean": observed_mean,
            "delta_std": delta_std,
            "delta_median": delta_median,
            "delta_min": delta_min,
            "delta_max": delta_max,
            "effect_size_paired_d": effect_size,
            "p_two_sided": p_two_sided,
            "p_less": p_less,
            "ci95_low": ci95_low,
            "ci95_high": ci95_high,
        }

    def _build_pairwise_comparison_rows(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """將同一 case 的三組結果對齊，建立 G2 對 G0/G1 的比較列。"""
        by_case: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for row in results:
            case_id = str(row.get("case_id", ""))
            group = str(row.get("group", ""))
            if case_id.startswith("============="):
                continue
            if case_id not in by_case:
                by_case[case_id] = {}
            by_case[case_id][group] = row

        rows: List[Dict[str, Any]] = []
        for case_id, group_map in by_case.items():
            if "G2" not in group_map:
                continue
            for baseline_group in ("G0", "G1"):
                if baseline_group not in group_map:
                    continue
                g2_row = group_map["G2"]
                baseline_row = group_map[baseline_group]
                g2_rate = float(g2_row.get("total_conflicts_per_100", 0.0))
                baseline_rate = float(baseline_row.get("total_conflicts_per_100", 0.0))
                g2_name_rate = float(g2_row.get("name_conflicts_per_100", 0.0))
                baseline_name_rate = float(baseline_row.get("name_conflicts_per_100", 0.0))
                g2_coref_rate = float(g2_row.get("coref_errors_per_100", 0.0))
                baseline_coref_rate = float(baseline_row.get("coref_errors_per_100", 0.0))
                g2_late_intro_rate = float(g2_row.get("late_introduced_characters_per_100", 0.0))
                baseline_late_intro_rate = float(baseline_row.get("late_introduced_characters_per_100", 0.0))
                g2_main_drop_rate = float(g2_row.get("main_character_drop_per_100", 0.0))
                baseline_main_drop_rate = float(baseline_row.get("main_character_drop_per_100", 0.0))
                g2_drift = float(g2_row.get("character_set_drift_mean", 0.0))
                baseline_drift = float(baseline_row.get("character_set_drift_mean", 0.0))
                delta_rate = g2_rate - baseline_rate
                delta_name = g2_name_rate - baseline_name_rate
                delta_coref = g2_coref_rate - baseline_coref_rate
                delta_late_intro = g2_late_intro_rate - baseline_late_intro_rate
                delta_main_drop = g2_main_drop_rate - baseline_main_drop_rate
                delta_drift = g2_drift - baseline_drift
                rows.append(
                    {
                        "case_id": case_id,
                        "comparison": f"G2_vs_{baseline_group}",
                        "g2_total_words": g2_row.get("total_words", 0),
                        "baseline_total_words": baseline_row.get("total_words", 0),
                        "g2_total_conflicts": g2_row.get("total_conflicts", 0),
                        "baseline_total_conflicts": baseline_row.get("total_conflicts", 0),
                        "g2_name_conflicts_per_100": g2_name_rate,
                        "baseline_name_conflicts_per_100": baseline_name_rate,
                        "delta_name_conflicts_per_100": delta_name,
                        "g2_coref_errors_per_100": g2_coref_rate,
                        "baseline_coref_errors_per_100": baseline_coref_rate,
                        "delta_coref_errors_per_100": delta_coref,
                        "g2_late_introduced_characters_per_100": g2_late_intro_rate,
                        "baseline_late_introduced_characters_per_100": baseline_late_intro_rate,
                        "delta_late_introduced_characters_per_100": delta_late_intro,
                        "g2_main_character_drop_per_100": g2_main_drop_rate,
                        "baseline_main_character_drop_per_100": baseline_main_drop_rate,
                        "delta_main_character_drop_per_100": delta_main_drop,
                        "g2_character_set_drift_mean": g2_drift,
                        "baseline_character_set_drift_mean": baseline_drift,
                        "delta_character_set_drift_mean": delta_drift,
                        "g2_total_conflicts_per_100": g2_rate,
                        "baseline_total_conflicts_per_100": baseline_rate,
                        "delta_total_conflicts_per_100": delta_rate,
                        "g2_better_total": delta_rate < 0,
                        "g2_better_name": delta_name < 0,
                        "g2_better_coref": delta_coref < 0,
                        "g2_better_late_intro": delta_late_intro < 0,
                        "g2_better_main_drop": delta_main_drop < 0,
                        "g2_better_drift": delta_drift < 0,
                    }
                )
        return rows

    def _pearson_correlation(self, xs: List[float], ys: List[float]) -> float:
        """計算 Pearson 相關係數，資料不足時回傳 0。"""
        if len(xs) != len(ys) or len(xs) < 2:
            return 0.0
        mx = statistics.mean(xs)
        my = statistics.mean(ys)
        num = 0.0
        den_x = 0.0
        den_y = 0.0
        for x, y in zip(xs, ys):
            dx = x - mx
            dy = y - my
            num += dx * dy
            den_x += dx * dx
            den_y += dy * dy
        den = math.sqrt(den_x * den_y)
        if den == 0:
            return 0.0
        return num / den

    def evaluate_directory(
        self,
        root_dir_str: str,
        output_csv: str = None,
        permutation_trials: int = 10000,
        permutation_seed: int = 12345,
        prefer_fair_story: bool = True,
        generate_raw_copy: bool = True,
    ):
        """
        Batch evaluates all cases in the given root directory and saves metrics to CSV.
        Assumes directory structure: root_dir / case_id / [G0, G1, G2] / story.txt
        prefer_fair_story=True 時，若存在 story_for_eval.txt 會優先使用（公平長度比較）。
        預設會額外再輸出一份原始 story.txt 版本（檔名加上 _raw）。
        """
        from pathlib import Path
        import csv
        
        root_dir = Path(root_dir_str)
        if not root_dir.exists():
            logger.error(f"Directory {root_dir} does not exist.")
            return

        mode_label = "fair_aligned" if prefer_fair_story else "raw_original"
        logger.info("Evaluation mode: %s", mode_label)

        results = []
        
        # Iterate through all case folders
        for case_dir in root_dir.iterdir():
            if not case_dir.is_dir():
                continue
                
            case_id = case_dir.name
            
            # Check if case is completely generated
            is_complete = True
            for group in ["G0", "G1", "G2"]:
                if not self._pick_story_file(case_dir, group, prefer_fair_story=prefer_fair_story).exists():
                    is_complete = False
                    break
                    
            if not is_complete:
                logger.warning(
                    "Case %s is incomplete for mode=%s (missing one or more story files). Skipping.",
                    case_id,
                    mode_label,
                )
                continue
            
            # We expect G0, G1, G2 subdirectories
            for group in ["G0", "G1", "G2"]:
                story_path = self._pick_story_file(case_dir, group, prefer_fair_story=prefer_fair_story)
                
                logger.info("Evaluating %s -> %s (%s)", case_id, group, story_path.name)
                with open(story_path, "r", encoding="utf-8") as f:
                    text = f.read()
                    
                report_str = self.evaluate(text, story_id=f"{case_id}_{group}")
                report = json.loads(report_str)
                metrics = report["metrics"]
                
                results.append({
                    "case_id": case_id,
                    "group": group,
                    "story_file": story_path.name,
                    "total_words": metrics.get("total_words", 0),
                    "name_conflicts": metrics["name_conflicts"],
                    "attribute_conflicts": metrics["attribute_conflicts"],
                    "coref_errors": metrics["coref_errors"],
                    "total_conflicts": metrics["total_conflicts"],
                    "severity_sum": metrics["severity_sum"],
                    # Keep full precision for downstream pairwise/permutation stats.
                    "name_conflicts_per_100": float(metrics.get("name_conflicts_per_100", 0.0)),
                    "attribute_conflicts_per_100": float(metrics.get("attribute_conflicts_per_100", 0.0)),
                    "coref_errors_per_100": float(metrics.get("coref_errors_per_100", 0.0)),
                    "total_conflicts_per_100": float(metrics.get("total_conflicts_per_100", 0.0)),
                    # B3: Complexity control metrics
                    "unique_characters": metrics.get("unique_character_count", 0),
                    "entity_mentions": metrics.get("entity_mention_count", 0),
                    "sentence_count": metrics.get("sentence_count", 0),
                    "pronoun_density": float(metrics.get("pronoun_density", 0.0)),
                    "distinct_name_forms_total": metrics.get("distinct_name_forms_total", 0),
                    "characters_with_multiple_name_forms": metrics.get("characters_with_multiple_name_forms", 0),
                    "late_introduced_characters": metrics.get("late_introduced_characters", 0),
                    "main_character_drop_count": metrics.get("main_character_drop_count", 0),
                    "character_set_drift_mean": float(metrics.get("character_set_drift_mean", 0.0)),
                    "late_introduced_characters_per_100": float(metrics.get("late_introduced_characters_per_100", 0.0)),
                    "main_character_drop_per_100": float(metrics.get("main_character_drop_per_100", 0.0)),
                })
                
        groups = ["G0", "G1", "G2"]

        # --- Group-level summary with SD ---
        group_summary_rows: List[Dict[str, Any]] = []
        for g in groups:
            group_rows = [r for r in results if r["group"] == g]
            if not group_rows:
                continue

            def _vals(key: str) -> List[float]:
                return [float(r.get(key, 0.0)) for r in group_rows]

            def _mean_sd(key: str) -> Tuple[float, float]:
                values = _vals(key)
                mean_v = statistics.mean(values) if values else 0.0
                sd_v = statistics.stdev(values) if len(values) > 1 else 0.0
                return mean_v, sd_v

            total_mean, total_sd = _mean_sd("total_conflicts_per_100")
            name_mean, name_sd = _mean_sd("name_conflicts_per_100")
            coref_mean, coref_sd = _mean_sd("coref_errors_per_100")
            attr_mean, attr_sd = _mean_sd("attribute_conflicts_per_100")
            late_mean, late_sd = _mean_sd("late_introduced_characters_per_100")
            drop_mean, drop_sd = _mean_sd("main_character_drop_per_100")
            drift_mean, drift_sd = _mean_sd("character_set_drift_mean")
            group_summary_rows.append(
                {
                    "group": g,
                    "n_cases": len(group_rows),
                    "total_conflicts_per_100_mean": round(total_mean, 4),
                    "total_conflicts_per_100_sd": round(total_sd, 4),
                    "name_conflicts_per_100_mean": round(name_mean, 4),
                    "name_conflicts_per_100_sd": round(name_sd, 4),
                    "coref_errors_per_100_mean": round(coref_mean, 4),
                    "coref_errors_per_100_sd": round(coref_sd, 4),
                    "attribute_conflicts_per_100_mean": round(attr_mean, 4),
                    "attribute_conflicts_per_100_sd": round(attr_sd, 4),
                    "late_introduced_characters_per_100_mean": round(late_mean, 4),
                    "late_introduced_characters_per_100_sd": round(late_sd, 4),
                    "main_character_drop_per_100_mean": round(drop_mean, 4),
                    "main_character_drop_per_100_sd": round(drop_sd, 4),
                    "character_set_drift_mean_mean": round(drift_mean, 4),
                    "character_set_drift_mean_sd": round(drift_sd, 4),
                }
            )
        
        # Mapping for output headers
        abs_mapping = {
            "case_id": "測試案例 (Case ID)",
            "group": "組別",
            "total_words": "總字數 (Total Words)",
            "name_conflicts": "命名衝突",
            "coref_errors": "代名詞錯誤",
            "total_conflicts": "總錯誤數",
            "severity_sum": "嚴重程度",
            "distinct_name_forms_total": "角色名稱變體總數",
            "characters_with_multiple_name_forms": "多稱謂角色數",
            "late_introduced_characters": "晚出角色數",
            "main_character_drop_count": "主角消失次數",
            "character_set_drift_mean": "角色集合漂移均值",
        }
        if self.enable_attribute_conflicts:
            abs_mapping["attribute_conflicts"] = "屬性衝突"
        
        norm_mapping = {
            "case_id": "測試案例 (Case ID)",
            "group": "組別",
            "story_file": "評估文本來源",
            "total_words": "總字數 (Total Words)",
            "name_conflicts_per_100": "每百字命名衝突",
            "coref_errors_per_100": "每百字代名詞錯誤",
            "total_conflicts_per_100": "每百字總錯誤率",
            "late_introduced_characters_per_100": "每百字晚出角色",
            "main_character_drop_per_100": "每百字主角消失",
            "character_set_drift_mean": "角色集合漂移均值",
        }
        if self.enable_attribute_conflicts:
            norm_mapping["attribute_conflicts_per_100"] = "每百字屬性衝突"

        # Write to CSV
        if output_csv is None:
            paper_dir = Path(__file__).parent / "paper"
            paper_dir.mkdir(parents=True, exist_ok=True)
            suffix = "" if prefer_fair_story else "_raw"
            output_abs_csv = paper_dir / f"evaluation_results_absolute_{root_dir.name}{suffix}.csv"
            output_norm_csv = paper_dir / f"evaluation_results_normalized_100w_{root_dir.name}{suffix}.csv"
        else:
            stem = Path(output_csv).stem
            mode_suffix = "" if prefer_fair_story else "_raw"
            output_abs_csv = Path(output_csv).with_name(f"{stem}{mode_suffix}_absolute.csv")
            output_norm_csv = Path(output_csv).with_name(f"{stem}{mode_suffix}_normalized_100w.csv")
        output_group_csv = output_abs_csv.with_name(f"{output_abs_csv.stem}_group_summary.csv")
            
        # 1. Write Absolute CSV
        # Use utf-8-sig so Excel automatically recognizes the encoding
        with open(output_abs_csv, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(abs_mapping.values()), extrasaction='ignore')
            writer.writeheader()
            for row in results:
                mapped_row = {abs_mapping[k]: v for k, v in row.items() if k in abs_mapping}
                writer.writerow(mapped_row)
                
        # 2. Write Normalized CSV
        with open(output_norm_csv, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(norm_mapping.values()), extrasaction='ignore')
            writer.writeheader()
            for row in results:
                mapped_row = {norm_mapping[k]: v for k, v in row.items() if k in norm_mapping}
                writer.writerow(mapped_row)

        # 3. Write Group Summary CSV (Mean + SD)
        group_mapping = {
            "group": "組別",
            "n_cases": "樣本數",
            "total_conflicts_per_100_mean": "每百字總錯誤率平均",
            "total_conflicts_per_100_sd": "每百字總錯誤率標準差",
            "name_conflicts_per_100_mean": "每百字命名衝突平均",
            "name_conflicts_per_100_sd": "每百字命名衝突標準差",
            "coref_errors_per_100_mean": "每百字代名詞錯誤平均",
            "coref_errors_per_100_sd": "每百字代名詞錯誤標準差",
            "late_introduced_characters_per_100_mean": "每百字晚出角色平均",
            "late_introduced_characters_per_100_sd": "每百字晚出角色標準差",
            "main_character_drop_per_100_mean": "每百字主角消失平均",
            "main_character_drop_per_100_sd": "每百字主角消失標準差",
            "character_set_drift_mean_mean": "角色集合漂移均值_平均",
            "character_set_drift_mean_sd": "角色集合漂移均值_標準差",
        }
        if self.enable_attribute_conflicts:
            group_mapping["attribute_conflicts_per_100_mean"] = "每百字屬性衝突平均"
            group_mapping["attribute_conflicts_per_100_sd"] = "每百字屬性衝突標準差"

        with open(output_group_csv, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(group_mapping.values()), extrasaction='ignore')
            writer.writeheader()
            for row in group_summary_rows:
                mapped_row = {group_mapping[k]: v for k, v in row.items() if k in group_mapping}
                writer.writerow(mapped_row)
                
        logger.info("Evaluation complete (%s).", mode_label)
        logger.info("Absolute results saved to: %s", output_abs_csv)
        logger.info("Normalized results saved to: %s", output_norm_csv)
        logger.info("Group summary saved to: %s", output_group_csv)

        # 4) Pairwise comparison CSV + 統計摘要 JSON
        pair_rows = self._build_pairwise_comparison_rows(results)
        output_pair_csv = output_abs_csv.with_name(f"{output_abs_csv.stem}_pairwise.csv")
        output_stats_json = output_abs_csv.with_name(f"{output_abs_csv.stem}_stats.json")
        pair_mapping = {
            "case_id": "測試案例 (Case ID)",
            "comparison": "比較組合",
            "g2_total_words": "G2總字數",
            "baseline_total_words": "基線組總字數",
            "g2_total_conflicts": "G2總錯誤數",
            "baseline_total_conflicts": "基線組總錯誤數",
            "g2_name_conflicts_per_100": "G2每百字命名衝突",
            "baseline_name_conflicts_per_100": "基線組每百字命名衝突",
            "delta_name_conflicts_per_100": "每百字命名衝突差值 (G2-基線)",
            "g2_coref_errors_per_100": "G2每百字代名詞錯誤",
            "baseline_coref_errors_per_100": "基線組每百字代名詞錯誤",
            "delta_coref_errors_per_100": "每百字代名詞錯誤差值 (G2-基線)",
            "g2_late_introduced_characters_per_100": "G2每百字晚出角色",
            "baseline_late_introduced_characters_per_100": "基線組每百字晚出角色",
            "delta_late_introduced_characters_per_100": "每百字晚出角色差值 (G2-基線)",
            "g2_main_character_drop_per_100": "G2每百字主角消失",
            "baseline_main_character_drop_per_100": "基線組每百字主角消失",
            "delta_main_character_drop_per_100": "每百字主角消失差值 (G2-基線)",
            "g2_character_set_drift_mean": "G2角色集合漂移均值",
            "baseline_character_set_drift_mean": "基線組角色集合漂移均值",
            "delta_character_set_drift_mean": "角色集合漂移均值差值 (G2-基線)",
            "g2_total_conflicts_per_100": "G2每百字總錯誤率",
            "baseline_total_conflicts_per_100": "基線組每百字總錯誤率",
            "delta_total_conflicts_per_100": "每百字總錯誤率差值 (G2-基線)",
            "g2_better_total": "G2是否較佳_總錯誤率",
            "g2_better_name": "G2是否較佳_命名衝突",
            "g2_better_coref": "G2是否較佳_代名詞錯誤",
            "g2_better_late_intro": "G2是否較佳_晚出角色",
            "g2_better_main_drop": "G2是否較佳_主角消失",
            "g2_better_drift": "G2是否較佳_角色集合漂移",
        }
        with open(output_pair_csv, "w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=list(pair_mapping.values()))
            writer.writeheader()
            for row in pair_rows:
                mapped_row = {pair_mapping[k]: v for k, v in row.items() if k in pair_mapping}
                writer.writerow(mapped_row)

        stats_payload: Dict[str, Any] = {
            "metric": "total_conflicts_per_100",
            "scoring_components": {
                "name_conflicts": True,
                "coref_errors": True,
                "attribute_conflicts": self.enable_attribute_conflicts,
                "structure_metrics_in_stats": self.include_structure_metrics_in_stats,
            },
            "permutation_trials": permutation_trials,
            "permutation_seed": permutation_seed,
            "group_summary": group_summary_rows,
            "comparisons": {},
            "complexity_correlation": {},
        }

        # Complexity correlation (optional analysis)
        all_total_rate = [float(r.get("total_conflicts_per_100", 0.0)) for r in results]
        all_unique_chars = [float(r.get("unique_characters", 0.0)) for r in results]
        all_pron_density = [float(r.get("pronoun_density", 0.0)) for r in results]
        all_sent_count = [float(r.get("sentence_count", 0.0)) for r in results]
        stats_payload["complexity_correlation"] = {
            "overall": {
                "r_total_vs_unique_characters": round(self._pearson_correlation(all_total_rate, all_unique_chars), 4),
                "r_total_vs_pronoun_density": round(self._pearson_correlation(all_total_rate, all_pron_density), 4),
                "r_total_vs_sentence_count": round(self._pearson_correlation(all_total_rate, all_sent_count), 4),
            },
            "by_group": {},
        }
        for g in groups:
            g_rows = [r for r in results if r.get("group") == g]
            xs = [float(r.get("total_conflicts_per_100", 0.0)) for r in g_rows]
            ys1 = [float(r.get("unique_characters", 0.0)) for r in g_rows]
            ys2 = [float(r.get("pronoun_density", 0.0)) for r in g_rows]
            ys3 = [float(r.get("sentence_count", 0.0)) for r in g_rows]
            stats_payload["complexity_correlation"]["by_group"][g] = {
                "r_total_vs_unique_characters": round(self._pearson_correlation(xs, ys1), 4),
                "r_total_vs_pronoun_density": round(self._pearson_correlation(xs, ys2), 4),
                "r_total_vs_sentence_count": round(self._pearson_correlation(xs, ys3), 4),
            }

        metric_specs = [
            ("total_conflicts_per_100", "delta_total_conflicts_per_100", "g2_better_total"),
            ("name_conflicts_per_100", "delta_name_conflicts_per_100", "g2_better_name"),
            ("coref_errors_per_100", "delta_coref_errors_per_100", "g2_better_coref"),
        ]
        if self.include_structure_metrics_in_stats:
            metric_specs.extend(
                [
                    ("late_introduced_characters_per_100", "delta_late_introduced_characters_per_100", "g2_better_late_intro"),
                    ("main_character_drop_per_100", "delta_main_character_drop_per_100", "g2_better_main_drop"),
                    ("character_set_drift_mean", "delta_character_set_drift_mean", "g2_better_drift"),
                ]
            )

        for comp in ("G2_vs_G0", "G2_vs_G1"):
            comp_rows = [r for r in pair_rows if r.get("comparison") == comp]
            comp_payload: Dict[str, Any] = {
                "n_cases": len(comp_rows),
                "metrics": {},
                "interpretation": "G2 better if mean_delta < 0 and one-sided p-value is small",
            }

            for metric_name, delta_key, win_key in metric_specs:
                deltas = [float(r.get(delta_key, 0.0)) for r in comp_rows]
                wins = sum(1 for r in comp_rows if bool(r.get(win_key)))
                test = self._paired_sign_permutation_test(
                    deltas,
                    trials=permutation_trials,
                    seed=permutation_seed,
                )
                comp_payload["metrics"][metric_name] = {
                    "n_cases": test["n"],
                    "g2_win_rate": (wins / len(comp_rows)) if comp_rows else 0.0,
                    "mean_delta": test["observed_mean"],
                    "delta_sd": test["delta_std"],
                    "delta_median": test["delta_median"],
                    "delta_min": test["delta_min"],
                    "delta_max": test["delta_max"],
                    "effect_size_paired_d": test["effect_size_paired_d"],
                    "p_value_two_sided": test["p_two_sided"],
                    "p_value_one_sided_g2_better": test["p_less"],
                    "ci95_mean_delta_from_permutation": [test["ci95_low"], test["ci95_high"]],
                }

            # Backward-compatible top-level fields for total metric
            total_metric = comp_payload["metrics"]["total_conflicts_per_100"]
            comp_payload["g2_win_rate"] = total_metric["g2_win_rate"]
            comp_payload["mean_delta_total_conflicts_per_100"] = total_metric["mean_delta"]
            comp_payload["p_value_two_sided"] = total_metric["p_value_two_sided"]
            comp_payload["p_value_one_sided_g2_better"] = total_metric["p_value_one_sided_g2_better"]

            stats_payload["comparisons"][comp] = comp_payload

        with open(output_stats_json, "w", encoding="utf-8") as fp:
            json.dump(stats_payload, fp, ensure_ascii=False, indent=2)

        logger.info("Pairwise results saved to: %s", output_pair_csv)
        logger.info("Statistical summary saved to: %s", output_stats_json)

        # 預設再輸出一份原始 story.txt 評估（不切齊字數）。
        if prefer_fair_story and generate_raw_copy:
            logger.info("Generating additional raw-original report set...")
            self.evaluate_directory(
                root_dir_str,
                output_csv=output_csv,
                permutation_trials=permutation_trials,
                permutation_seed=permutation_seed,
                prefer_fair_story=False,
                generate_raw_copy=False,
            )


if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description="Evaluate story consistency")
    parser.add_argument("--dir", type=str, help="Directory containing generated cases (e.g., output/experiments)", default=None)
    parser.add_argument("--model", type=str, help="SpaCy model to use (default: en_core_web_sm)", default="en_core_web_sm")
    parser.add_argument("--coref_model", type=str, help="SpaCy experimental coref model to use (default: en_coreference_web_trf)", default="en_coreference_web_trf")
    parser.add_argument("--perm_trials", type=int, default=10000, help="Permutation test trials for pairwise significance")
    parser.add_argument("--perm_seed", type=int, default=12345, help="Random seed for permutation test")
    parser.add_argument(
        "--include_attribute_conflicts",
        action="store_true",
        help="Enable attribute conflict detection (disabled by default).",
    )
    parser.add_argument(
        "--late_intro_max_mentions",
        type=int,
        default=2,
        help="Late-introduced character mention threshold (default: 2).",
    )
    parser.add_argument(
        "--include_structure_metrics_in_stats",
        action="store_true",
        help="Include structure metrics in pairwise permutation tests (disabled by default).",
    )
    args = parser.parse_args()
    
    print("Initializing evaluator...")
    try:
        evaluator = ConsistencyEvaluator(
            model_name=args.model,
            coref_model=args.coref_model,
            enable_attribute_conflicts=args.include_attribute_conflicts,
            late_intro_max_mentions=args.late_intro_max_mentions,
            include_structure_metrics_in_stats=args.include_structure_metrics_in_stats,
        )
    except Exception as e:
        print(f"Failed to load spacy model or dependency: {e}")
        sys.exit(1)

    def _resolve_default_experiment_dir():
        root = Path(__file__).parent / "output" / "experiments"
        if not root.exists():
            return None
        return root

    target_dir = Path(args.dir) if args.dir else _resolve_default_experiment_dir()

    if target_dir:
        print(f"Evaluating directory: {target_dir}")
        evaluator.evaluate_directory(
            str(target_dir),
            permutation_trials=args.perm_trials,
            permutation_seed=args.perm_seed,
        )
    else:
        print("No experiment directory found. Please run scripts/run_experiment.py first, or pass --dir explicitly.")
        sys.exit(1)
