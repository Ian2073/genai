# knowledge_bases.py - 多知識庫整合事實檢測系統
"""
整合多個開放知識庫進行事實驗證：
1. Wikidata - 結構化知識庫
2. DBpedia - 維基百科結構化數據
3. ConceptNet - 常識知識網絡
4. 本地知識庫 - 快速查詢
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import yaml


logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    """知識庫查詢結果"""

    source: str  # 知識庫來源
    verdict: str  # supported, refuted, uncertain
    confidence: float  # 置信度 0-1
    evidence: List[str]  # 證據列表
    raw_data: Dict[str, Any]  # 原始數據


CacheKey = Tuple[str, str, Tuple[str, ...]]
CacheValue = Tuple[float, Optional[KnowledgeResult]]


class MultiKnowledgeBase:
    """多知識庫整合檢測器"""

    def __init__(
        self,
        wikidata_endpoint: str = "https://query.wikidata.org/sparql",
        dbpedia_endpoint: str = "https://dbpedia.org/sparql",
        timeout: float = 5.0,
        rate_limit_delay: float = 0.2,
        cache_ttl: int = 3600,
        max_entities: int = 3,
        local_matcher: Optional["LocalCategoryMatcher"] = None,
    ) -> None:
        self.wikidata_endpoint = wikidata_endpoint
        self.dbpedia_endpoint = dbpedia_endpoint
        self.timeout = float(timeout)
        self.rate_limit_delay = max(0.0, float(rate_limit_delay))
        self.cache_ttl = max(int(cache_ttl), 60)
        self.max_entities = max(1, int(max_entities))

        self._cache: Dict[CacheKey, CacheValue] = {}
        self.local_categories = local_matcher or LocalCategoryMatcher()

        # 載入配置的詞彙
        self.stop_words = {word.lower() for word in self._load_keywords("kb.stop_words")}
        self.important_entities = tuple(self._load_important_entities())
    
    def _load_keywords(self, category: str) -> List[str]:
        """從配置文件載入關鍵詞"""
        try:
            return self.local_categories.get_keywords(category)
        except Exception:  # noqa: BLE001
            return []
    
    def _load_important_entities(self) -> List[str]:
        """載入重要實體列表"""
        entities: List[str] = []
        for subcategory in ['scientists', 'universities', 'locations', 'organizations', 'landmarks']:
            try:
                entities.extend(self.local_categories.get_keywords(f"kb.important_entities.{subcategory}"))
            except Exception:  # noqa: BLE001
                continue
        return sorted({entity.strip() for entity in entities if isinstance(entity, str) and entity.strip()})
    
    def verify_fact(self, claim: str, claim_type: str = "general") -> List[KnowledgeResult]:
        """綜合多個知識庫驗證事實."""

        if not claim or not claim.strip():
            return []

        entities = self._extract_entities(claim)
        results: List[KnowledgeResult] = []

        try:
            wikidata_result = self._query_wikidata(claim, claim_type, entities)
            if wikidata_result:
                results.append(wikidata_result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Wikidata查詢失敗: %s", exc)

        try:
            dbpedia_result = self._query_dbpedia(claim, claim_type, entities)
            if dbpedia_result:
                results.append(dbpedia_result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DBpedia查詢失敗: %s", exc)

        return results
    
    def _query_wikidata(self, claim: str, claim_type: str, entities: List[str]) -> Optional[KnowledgeResult]:
        """查詢Wikidata知識庫"""
        if not entities:
            return None
        
        # 構建SPARQL查詢
        sparql_query = self._build_wikidata_query(entities, claim_type)
        
        return self._run_sparql_query(
            endpoint=self.wikidata_endpoint,
            query=sparql_query,
            claim=claim,
            analyzer=self._analyze_wikidata_results,
            cache_key=("wikidata", claim_type, tuple(entities)),
        )
    
    def _query_dbpedia(self, claim: str, claim_type: str, entities: List[str]) -> Optional[KnowledgeResult]:
        """查詢DBpedia知識庫"""
        if not entities:
            return None
        
        # 構建SPARQL查詢
        sparql_query = self._build_dbpedia_query(entities, claim_type)
        
        return self._run_sparql_query(
            endpoint=self.dbpedia_endpoint,
            query=sparql_query,
            claim=claim,
            analyzer=self._analyze_dbpedia_results,
            cache_key=("dbpedia", claim_type, tuple(entities)),
        )

    def _run_sparql_query(
        self,
        endpoint: str,
        query: str,
        claim: str,
    analyzer: Callable[[Dict[str, Any], str], KnowledgeResult],
    cache_key: CacheKey,
    ) -> Optional[KnowledgeResult]:
        if not query.strip():
            return None

        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        headers = {
            "User-Agent": "FactChecker/1.0 (https://example.com/contact)",
            "Accept": "application/sparql-results+json",
        }

        try:
            response = requests.get(
                endpoint,
                params={"query": query, "format": "json"},
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                data = response.json()
                result = analyzer(data, claim)
                self._cache[cache_key] = (now, result)
                return result
            logger.warning("SPARQL查詢失敗(%s): %s", response.status_code, response.text[:200])
            self._cache[cache_key] = (now, None)
        except Exception as exc:  # noqa: BLE001
            logger.error("SPARQL查詢錯誤: %s", exc)
            self._cache[cache_key] = (now, None)
        finally:
            if self.rate_limit_delay:
                time.sleep(self.rate_limit_delay)

        return None
    
    
    def _extract_entities(self, claim: str) -> List[str]:
        """從聲明中提取實體名稱"""
        import re

        proper_nouns = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", claim)
        if not proper_nouns:
            return []

        seen = set()
        filtered: List[str] = []
        stop_words = self.stop_words
        for noun in proper_nouns:
            key = noun.lower()
            if key in seen or key in stop_words:
                continue
            seen.add(key)
            filtered.append(noun)

        claim_lower = claim.lower()
        priority = [entity for entity in self.important_entities if entity.lower() in claim_lower]
        limit = self.max_entities
        if priority:
            return priority[:limit]

        return filtered[:limit]
    
    
    def _build_wikidata_query(self, entities: List[str], claim_type: str) -> str:
        """構建Wikidata SPARQL查詢"""
        if claim_type == "biographical":
            # 人物相關查詢 - 更詳細的信息
            entity = entities[0] if entities else "Unknown"
            return f"""
            SELECT ?item ?itemLabel ?birthDate ?deathDate ?occupation ?occupationLabel ?award ?awardLabel ?discovery ?discoveryLabel ?nationality ?nationalityLabel WHERE {{
                ?item rdfs:label "{entity}"@en .
                OPTIONAL {{ ?item wdt:P569 ?birthDate . }}
                OPTIONAL {{ ?item wdt:P570 ?deathDate . }}
                OPTIONAL {{ ?item wdt:P106 ?occupation . }}
                OPTIONAL {{ ?item wdt:P166 ?award . }}
                OPTIONAL {{ ?item wdt:P61 ?discovery . }}
                OPTIONAL {{ ?item wdt:P27 ?nationality . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 3
            """
        elif claim_type == "geographical":
            # 地理相關查詢 - 更詳細的信息
            entity = entities[0] if entities else "Unknown"
            return f"""
            SELECT ?item ?itemLabel ?height ?location ?country ?countryLabel ?coordinates ?continent ?continentLabel WHERE {{
                ?item rdfs:label "{entity}"@en .
                OPTIONAL {{ ?item wdt:P2044 ?height . }}
                OPTIONAL {{ ?item wdt:P276 ?location . }}
                OPTIONAL {{ ?item wdt:P17 ?country . }}
                OPTIONAL {{ ?item wdt:P625 ?coordinates . }}
                OPTIONAL {{ ?item wdt:P30 ?continent . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 3
            """
        elif claim_type == "scientific":
            # 科學相關查詢
            entity = entities[0] if entities else "Unknown"
            return f"""
            SELECT ?item ?itemLabel ?discoveredBy ?discoveredByLabel ?inventedBy ?inventedByLabel ?year ?yearLabel WHERE {{
                ?item rdfs:label "{entity}"@en .
                OPTIONAL {{ ?item wdt:P61 ?discoveredBy . }}
                OPTIONAL {{ ?item wdt:P176 ?inventedBy . }}
                OPTIONAL {{ ?item wdt:P575 ?year . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 5
            """
        else:
            # 通用查詢 - 更詳細的信息
            entity = entities[0] if entities else "Unknown"
            return f"""
            SELECT ?item ?itemLabel ?description ?instanceOf ?instanceOfLabel WHERE {{
                ?item rdfs:label "{entity}"@en .
                OPTIONAL {{ ?item schema:description ?description . }}
                OPTIONAL {{ ?item wdt:P31 ?instanceOf . }}
                SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
            }}
            LIMIT 5
            """
    
    def _build_dbpedia_query(self, entities: List[str], claim_type: str) -> str:
        """構建DBpedia SPARQL查詢"""
        if not entities:
            return ""
        
        # 清理實體名稱，確保符合DBpedia格式
        entity = entities[0].replace(" ", "_").replace("'", "").replace(",", "").replace(".", "")
        
        return f"""
        PREFIX dbr: <http://dbpedia.org/resource/>
        PREFIX dbo: <http://dbpedia.org/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        
        SELECT ?property ?value ?label WHERE {{
            {{
                dbr:{entity} ?property ?value .
                OPTIONAL {{ dbr:{entity} rdfs:label ?label . }}
                FILTER(isLiteral(?value))
            }}
            UNION
            {{
                ?subject rdfs:label "{entities[0]}"@en .
                ?subject ?property ?value .
                OPTIONAL {{ ?subject rdfs:label ?label . }}
                FILTER(isLiteral(?value))
            }}
        }}
        LIMIT 15
        """
    
    def _analyze_wikidata_results(self, data: Dict, claim: str) -> KnowledgeResult:
        """智能分析Wikidata查詢結果"""
        bindings = data.get('results', {}).get('bindings', [])
        
        if not bindings:
            return KnowledgeResult(
                source="Wikidata",
                verdict="uncertain",
                confidence=0.1,
                evidence=["未找到相關Wikidata條目"],
                raw_data=data
            )
        
        # 智能分析結果
        evidence = []
        confidence = 0.6  # 基礎置信度
        
        # 提取所有可用的屬性信息
        entity_info = {}
        for binding in bindings:
            for key, value in binding.items():
                if key.endswith('Label') and key != 'itemLabel':
                    prop_name = key.replace('Label', '')
                    prop_value = value['value']
                    entity_info[prop_name] = prop_value
                elif key == 'itemLabel':
                    entity_info['name'] = value['value']
        
        # 構建詳細證據
        if 'name' in entity_info:
            evidence.append(f"實體: {entity_info['name']}")
            confidence += 0.2
        
        # 添加具體屬性信息
        for prop, value in entity_info.items():
            if prop != 'name':
                evidence.append(f"{prop}: {value}")
                confidence += 0.1
        
        # 確定最終判決
        verdict = "supported" if confidence > 0.7 else "uncertain"
        
        return KnowledgeResult(
            source="Wikidata",
            verdict=verdict,
            confidence=min(0.95, confidence),
            evidence=evidence,
            raw_data=data
        )
    
    def _analyze_dbpedia_results(self, data: Dict, claim: str) -> KnowledgeResult:
        """智能分析DBpedia查詢結果"""
        bindings = data.get('results', {}).get('bindings', [])
        
        if not bindings:
            return KnowledgeResult(
                source="DBpedia",
                verdict="uncertain",
                confidence=0.1,
                evidence=["未找到相關DBpedia條目"],
                raw_data=data
            )
        
        evidence = []
        confidence = 0.5  # 基礎置信度
        
        # 智能分析屬性值
        for binding in bindings:
            if 'value' in binding:
                value = binding['value']['value']
                property_uri = binding.get('property', {}).get('value', '')
                
                # 智能提取屬性名稱
                prop_name = self._extract_property_name(property_uri)
                
                # 根據屬性類型提供更有意義的證據
                if 'birthDate' in prop_name or 'birth' in prop_name:
                    evidence.append(f"出生日期: {value}")
                    confidence += 0.3
                elif 'deathDate' in prop_name or 'death' in prop_name:
                    evidence.append(f"逝世日期: {value}")
                    confidence += 0.3
                elif 'abstract' in prop_name or 'description' in prop_name:
                    if len(value) > 50:
                        evidence.append(f"描述: {value[:100]}...")
                        confidence += 0.2
                elif 'label' in prop_name:
                    evidence.append(f"標籤: {value}")
                    confidence += 0.1
                elif 'discovered' in prop_name or 'invented' in prop_name:
                    evidence.append(f"發現/發明: {value}")
                    confidence += 0.3
                elif 'award' in prop_name or 'prize' in prop_name:
                    evidence.append(f"獎項: {value}")
                    confidence += 0.3
                else:
                    evidence.append(f"{prop_name}: {value}")
                    confidence += 0.1
        
        verdict = "supported" if confidence > 0.6 else "uncertain"
        
        return KnowledgeResult(
            source="DBpedia",
            verdict=verdict,
            confidence=min(0.90, confidence),
            evidence=evidence,
            raw_data=data
        )
    
    def _extract_property_name(self, property_uri: str) -> str:
        """智能提取屬性名稱"""
        if not property_uri:
            return "屬性"
        
        # 從URI中提取屬性名稱
        if '#' in property_uri:
            return property_uri.split('#')[-1]
        elif '/' in property_uri:
            return property_uri.split('/')[-1]
        else:
            return "屬性"
    
    
    def aggregate_results(self, results: List[KnowledgeResult]) -> Tuple[str, float, List[str]]:
        """聚合多個知識庫的結果"""
        if not results:
            return "uncertain", 0.1, ["未找到任何知識庫支持"]
        
        weights = {
            "Wikidata": 1.0,
            "DBpedia": 0.9,
        }

        total_weight = 0.0
        weighted_confidence = 0.0
        support_weight = 0.0
        refute_weight = 0.0
        evidence: List[str] = []

        for result in results:
            weight = float(weights.get(result.source, 0.5))
            contribution = result.confidence * weight
            total_weight += weight
            weighted_confidence += contribution

            if result.verdict == "supported":
                support_weight += contribution
            elif result.verdict == "refuted":
                refute_weight += contribution

            for ev in result.evidence:
                evidence.append(f"[{result.source}] {ev}")

        final_confidence = weighted_confidence / total_weight if total_weight else 0.1
        final_confidence = max(0.0, min(1.0, final_confidence))

        if refute_weight > support_weight and refute_weight >= 0.6:
            verdict = "refuted"
        elif support_weight >= refute_weight and support_weight >= 0.55:
            verdict = "supported"
        else:
            verdict = "uncertain"

        # 去重並限制證據數量
        unique_evidence: List[str] = []
        seen = set()
        for item in evidence:
            if item in seen:
                continue
            seen.add(item)
            unique_evidence.append(item)
            if len(unique_evidence) == 10:
                break

        return verdict, final_confidence, unique_evidence

    def clear_cache(self) -> None:
        """清空 SPARQL 查詢快取。"""

        self._cache.clear()

    def is_local_category_match(self, category: str, text: str) -> bool:
        return self.local_categories.is_match(category, text)

    def get_local_keywords(self, category: str) -> List[str]:
        return self.local_categories.get_keywords(category)

    def list_local_categories(self, prefix: Optional[str] = None) -> List[str]:
        return self.local_categories.get_category_names(prefix)


class LocalCategoryMatcher:
    """從外部設定載入的本地常識分類匹配器"""

    def __init__(self, config_path: Optional[str] = None):
        base_path = os.path.dirname(__file__)
        self.config_path = config_path or os.path.join(base_path, "config", "local_categories.yaml")
        self.categories = self._load_categories()

    def _load_categories(self) -> Dict[str, List[str]]:
        if not os.path.exists(self.config_path):
            logger.warning("未找到本地分類設定檔，將回傳空分類：%s", self.config_path)
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}
        except Exception as exc:
            logger.error("載入本地分類設定檔失敗：%s", exc)
            return {}

        categories_root = data.get("categories", data)
        if not isinstance(categories_root, dict):
            logger.error("本地分類設定檔格式錯誤，預期為 dict：%s", type(categories_root).__name__)
            return {}

        normalized = self._normalize_categories(categories_root)
        return normalized

    def _normalize_categories(self, tree: Dict[str, Any], prefix: str = "") -> Dict[str, List[str]]:
        normalized: Dict[str, List[str]] = {}
        for name, value in tree.items():
            key = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
            if isinstance(value, dict):
                normalized.update(self._normalize_categories(value, key))
                continue

            if isinstance(value, list):
                cleaned = sorted({kw.lower().strip() for kw in value if isinstance(kw, str) and kw.strip()})
                if cleaned:
                    normalized[key] = cleaned
                else:
                    logger.debug("類別 %s 的關鍵字列表為空", key)
            else:
                logger.debug("忽略類別 %s 的非列表值: %r", key, value)

        return normalized

    def is_match(self, category: str, text: str) -> bool:
        keywords = self.categories.get(category, [])
        if not keywords or not text:
            return False

        lowered = text.lower()
        return any(keyword in lowered for keyword in keywords)

    def get_keywords(self, category: str) -> List[str]:
        return list(self.categories.get(category, []))

    def get_category_names(self, prefix: Optional[str] = None) -> List[str]:
        if prefix is None:
            return sorted(self.categories.keys())

        normalized_prefix = prefix.rstrip('.')
        return sorted(name for name in self.categories if name.startswith(normalized_prefix))

    def reload(self) -> None:
        self.categories = self._load_categories()

# 使用範例
if __name__ == "__main__":
    kb = MultiKnowledgeBase()
    
    # 測試事實檢測
    test_claims = [
        "Marie Curie won the Nobel Prize in Physics in 1903",
        "Mount Everest is 8,849 meters high",
        "Charles Darwin published On the Origin of Species in 1859"
    ]
    
    for claim in test_claims:
        print(f"\n檢測聲明: {claim}")
        results = kb.verify_fact(claim, "biographical")
        verdict, confidence, evidence = kb.aggregate_results(results)
        
        print(f"結果: {verdict} (置信度: {confidence:.2f})")
        for ev in evidence:
            print(f"  - {ev}")
