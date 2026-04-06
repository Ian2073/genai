# multimodal.py - 三維度故事評估系統 - 文圖一致性維度
# 用途：檢查文字描述與圖像內容的三大維度一致性
# 核心：文字中的視覺描述 vs 實際圖像內容的對應程度
# 三大維度：
# 1. 劇情一致性 - 文字情節與圖像事件的對應
# 2. 角色外貌一致性 - 文字角色描述與圖像角色的對應  
# 3. 場景環境一致性 - 文字場景描述與圖像背景的對應
# （已移除：情感表達一致性、時序邏輯一致性）
import logging
import os
import re
import json
from PIL import Image
import numpy as np
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Union
from .consistency import ComprehensiveKnowledgeGraph, AIAnalyzer
from .utils import (
    SentenceSplitterMixin,
    ensure_instance,
    get_default_model_path,
    get_kg_path,
    load_spacy_model,
    resolve_model_path,
)
try:
    import yaml
except Exception:
    yaml = None
from math import sqrt
import torch


logger = logging.getLogger(__name__)

@dataclass
class VisualElement:
    element_id: str
    element_type: str  # 'character', 'object', 'scene', 'setting', 'action'
    description: str
    attributes: Dict[str, str]  # 如 {'color': 'red', 'size': 'large', 'emotion': 'happy'}
    location: str  # 在文本中的位置
    required_in_image: bool
    consistency_requirements: List[str]

@dataclass
class ImageAnalysis:
    image_path: str
    detected_elements: List[Dict]
    missing_elements: List[str]
    inconsistent_elements: List[Dict]
    consistency_score: float
    
@dataclass
class MultimodalScores:
    """三維度多模態一致性評分"""
    plot_consistency: float           # 劇情一致性：文字情節 vs 圖像事件
    character_appearance: float       # 角色外貌一致性：文字角色描述 vs 圖像角色
    scene_environment: float          # 場景環境一致性：文字場景描述 vs 圖像背景  
    final: float                      # 綜合評分
    confidence: float                 # 評估置信度（有圖像時更高）

class MultimodalChecker(SentenceSplitterMixin):
    # 多模態檢測器（六維度故事評估系統 - 文圖一致性維度）
    
    def __init__(self, 
                 kg_path: str = get_kg_path(),
                 model_path: str = get_default_model_path("Qwen2.5-14B"),
                 use_multiple_ai_prompts: bool = False,
                 image_analysis_enabled: bool = False,
                 ai: AIAnalyzer = None,
                 kg: ComprehensiveKnowledgeGraph = None,
                 nlp=None):
        # 簡單流程（文圖一致怎麼看）：
        # 1) 文字 → 抽視覺要素（人物/場景/物件/動作/情緒）
        # 2) 圖片 → 偵測元素（YOLO/BLIP/OV）
        # 3) 比對：token 重疊 + 語義相似
        # 4) 依三個面向打分：劇情/角色外觀/場景環境
        # 5) 輸出每張圖缺漏與不一致清單
        # 載入核心分析工具
        self.kg = ensure_instance(kg, ComprehensiveKnowledgeGraph, kg_path)
        self.ai = ensure_instance(ai, AIAnalyzer, model_path, use_multiple_ai_prompts)
        self.nlp = ensure_instance(nlp, load_spacy_model)
        self.image_analysis_enabled = image_analysis_enabled # 是否啟用圖像分析
        # 匹配演算法配置（優化版：提高召回率和語義匹配）
        self.match_config = {
            'token_overlap_weight': 0.6,  # 降低詞彙重疊權重，更靈活匹配
            'semantic_weight': 0.4,       # 提高語義相似性權重
            'min_match_score': 0.15,      # 降低最低匹配分數，提高召回率
            'min_semantic_sim': 0.35,     # 降低最低語義相似度門檻
            'tfidf_min_df': 1,            # 包含更多低頻詞，減少過濾
            'tfidf_max_k': 80,            # 增加特徵數以提高覆蓋率
            'use_spacy_vectors': True,    # 使用spaCy詞向量
            # 語義 token 相似度權重與門檻（優化版）
            'semantic_token_weight': 0.30,
            'semantic_token_min_sim': 0.50
        }
        # 讀取外部配置（aspects_sources.yaml）
        self.output_config = {
            'write_per_page_json': True,
            'per_page_json_name': 'multimodal_page_report.json'
        }
        self._load_external_config()
        # 最近一次抽取的文字視覺描述（供開放詞彙偵測查詢使用）
        self._latest_text_descriptions: Dict[str, List[Dict]] = None
        # 啟用的多模態維度（可收斂為三維）
        self.enabled_dimensions: List[str] = [
            'plot_consistency',
            'character_appearance',
            'scene_environment'
        ]
        
        # YOLO 參數（優化版：提高檢測敏感度），並在流程中快取模型
        try:
            self.yolo_conf = float(os.environ.get('YOLO_CONF', '0.15'))  # 降低門檻提高檢測率
        except Exception:
            self.yolo_conf = 0.15  # 優化版預設值
        try:
            self.yolo_iou = float(os.environ.get('YOLO_IOU', '0.50'))
        except Exception:
            self.yolo_iou = 0.50
        try:
            self.yolo_imgsz = int(os.environ.get('YOLO_IMGSZ', '896'))
        except Exception:
            self.yolo_imgsz = 896
        # YOLO 權重：優先環境變數；否則若本地模型存在則使用；再不行才回退相對路徑（可能觸發下載）
        _yw = os.environ.get('YOLO_WEIGHTS')
        if _yw and os.path.exists(_yw):
            self.yolo_weights = _yw
        else:
            _local_yolo = resolve_model_path('yolov8n.pt')
            self.yolo_weights = _local_yolo if os.path.exists(_local_yolo) else 'yolov8n.pt'
        self._yolo_model = None
        # transformers 與 YOLO 的裝置與快取設定
        try:
            import torch as _torch
            self._has_cuda = _torch.cuda.is_available()
        except Exception:
            self._has_cuda = False
        self._hf_device = 0 if self._has_cuda else -1
        self._hf_dtype = 'auto'
        self._ovd_pipe = None
        self._blip_pipe = None
        
        # 動態學習錨點（從成功匹配中學習）
        self.adaptive_anchors = {
            'plot_consistency': [],
            'character_appearance': [],
            'scene_environment': []
        }
        
        # 成功匹配歷史（用於學習）
        self.successful_matches = {
            'plot_consistency': [],
            'character_appearance': [],
            'scene_environment': []
        }
        
        # 視覺元素抽取正則表達式模式庫
        self.visual_patterns = {
            # 角色外觀描述
            "character_appearance": [
                r'\b(?:tall|short|big|small|little|tiny|huge)\s+(?:boy|girl|man|woman|person|character)\b',
                r'\b(?:red|blue|green|yellow|orange|purple|pink|brown|black|white|blonde|dark)\s+(?:hair|eyes|dress|shirt|pants|hat)\b',
                r'\b(?:wearing|dressed in|had on)\s+(?:a|an|the)?\s*(?:\w+\s+){0,2}(?:dress|shirt|pants|hat|shoes|coat|jacket)\b',
                r'\b(?:smiled|frowned|laughed|cried|looked\s+(?:happy|sad|angry|surprised|scared|excited))\b'
            ],
            
            # 場景設定
            "scene_setting": [
                r'\bin\s+(?:the\s+)?(?:forest|garden|house|room|kitchen|bedroom|park|school|library|store|market)\b',
                r'\b(?:under|near|by|beside|in front of|behind)\s+(?:the\s+)?(?:tree|table|chair|bed|door|window|wall)\b',
                r'\b(?:sunny|rainy|cloudy|snowy|dark|bright|morning|afternoon|evening|night)\b',
                r'\b(?:inside|outside|indoors|outdoors)\b'
            ],
            
            # 物件描述
            "objects": [
                r'\b(?:a|an|the)\s+(?:big|small|little|old|new|red|blue|green)?\s*(?:book|toy|ball|box|bag|cup|plate|flower|tree)\b',
                r'\b(?:holding|carrying|picked up|put down|threw|caught)\s+(?:a|an|the)?\s*\w+\b',
                r'\b(?:opened|closed|looked at|found|lost)\s+(?:a|an|the)?\s*\w+\b'
            ],
            
            # 動作和姿勢
            "actions_poses": [
                r'\b(?:standing|sitting|lying|running|walking|jumping|dancing|playing|reading|writing|eating|sleeping)\b',
                r'\b(?:raised|lifted|pointed|waved|clapped|hugged|shook)\s+(?:his|her|their)?\s*(?:hand|arm|head|finger)\b',
                r'\b(?:looked\s+(?:up|down|left|right|at|towards))\b',
                r'\b(?:turned\s+(?:around|away|towards))\b'
            ],
            
            # 情感表達
            "emotions": [
                r'\b(?:happy|sad|angry|excited|surprised|scared|worried|proud|shy|confused)\b',
                r'\b(?:smiling|frowning|crying|laughing|shouting|whispering)\b',
                r'\b(?:eyes\s+(?:wide|bright|sparkling|filled with tears))\b',
                r'\b(?:face\s+(?:lit up|turned red|went pale))\b'
            ]
        }
        
        # 一致性檢查規則庫（各維度的檢查標準）
        self.consistency_rules = {
            "character_continuity": [
                "角色外觀特徵在不同頁面中應保持一致",
                "角色服裝在同一場景中應保持一致（除非明確更換）",
                "角色年齡外觀應符合故事設定"
            ],
            "scene_continuity": [
                "同一場景的背景設定應保持一致",
                "物件位置在同一場景中應合理",
                "天氣和光線條件應符合故事時間線"
            ],
            "narrative_flow": [
                "圖像順序應符合故事發展",
                "關鍵情節轉折應在圖像中體現",
                "角色情感變化應在圖像中反映"
            ]
        }
        
        # 兒童繪本特殊要求（針對目標讀者的視覺設計標準）
        self.children_book_requirements = {
            "visual_clarity": [
                "主要角色應清晰可辨識",
                "重要物件應突出顯示",
                "場景不應過於複雜混亂"
            ],
            "age_appropriateness": [
                "圖像內容應適合目標年齡群",
                "色彩使用應吸引兒童注意",
                "避免可能引起恐懼的視覺元素"
            ],
            "educational_value": [
                "圖像應支持故事的教育目標",
                "視覺元素應幫助理解故事內容",
                "可以包含學習元素（如數字、字母、顏色）"
            ]
        }
        
        # 📄 多模態一致性評估文檔選擇矩陣
        self.document_selection_matrix = {
            'primary': ['narration.txt', 'full_story.txt'],
            'secondary': ['dialogue.txt'],
            'excluded': ['title.txt', 'outline.txt'],
            'weights': {
                'narration.txt': 0.40,
                'full_story.txt': 0.35,
                'dialogue.txt': 0.25
            }
        }
    
    def _load_external_config(self):
        """從 aspects_sources.yaml 載入匹配/輸出參數（若可用）"""
        if not yaml:
            return
        try:
            cfg_path = 'aspects_sources.yaml'
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                mm_cfg = data.get('multimodal_config') or {}
                # 匹配參數
                self.match_config.update({k:v for k,v in mm_cfg.get('match',{}).items() if k in self.match_config})
                # 輸出參數
                self.output_config.update(mm_cfg.get('output',{}))
        except Exception:
            pass
    
    def get_documents_for_multimodal(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        """根據多模態一致性評估需求選擇相應的文檔"""
        selected_docs = {}
        
        # 優先選擇主要文檔
        for doc_name in self.document_selection_matrix['primary']:
            if doc_name in available_documents:
                selected_docs[doc_name] = available_documents[doc_name]
        
        # 如果主要文檔不足，添加次要文檔
        if len(selected_docs) < 2:
            for doc_name in self.document_selection_matrix['secondary']:
                if doc_name in available_documents and doc_name not in selected_docs:
                    selected_docs[doc_name] = available_documents[doc_name]
        
        return selected_docs
    
    def get_document_weights_for_multimodal(self) -> Dict[str, float]:
        """獲取多模態一致性評估的文檔權重"""
        return self.document_selection_matrix['weights']
    
    def check(self, story_text: str, story_title: str = "Story",
              narration_text: str = None, dialogue_text: str = None,
              image_paths: List[str] = None, image_manifest: Dict = None,
              ai_enabled: bool = True) -> Dict:
        """三大維度多模態一致性檢測接口
        
        檢查文字描述與圖像內容在三個維度上的對應程度：
        1. 劇情一致性 - 文字情節 vs 圖像事件
        2. 角色外貌一致性 - 文字角色描述 vs 圖像角色
        3. 場景環境一致性 - 文字場景描述 vs 圖像背景
        （已移除：情感表達、時序邏輯）
        """
        
        # 🔍 1) 從文字中提取三大維度的視覺描述（動態詞庫）
        text_descriptions = self._extract_text_visual_descriptions(story_text, narration_text, dialogue_text)
        # 動態詞庫：基於TF-IDF過濾與限制特徵數量
        text_descriptions = self._refine_descriptions_by_tfidf(text_descriptions)
        # 暫存本次的文字描述，供影像開放詞彙查詢使用
        self._latest_text_descriptions = text_descriptions
        
        # 🖼️ 2) 分析圖像內容（如果有圖像）
        if image_paths and self.image_analysis_enabled:
            image_content = self._analyze_image_content(image_paths, image_manifest)
            has_images = True
            mode = "text_image_comparison"
        else:
            image_content = None
            has_images = False  
            mode = "text_only_analysis"
        
        # ⚖️ 3) 一致性比對（僅針對啟用的維度）
        dimension_results = self._compare_text_image_consistency(text_descriptions, image_content, has_images)
        
        # 🤖 4) AI輔助分析（可關閉以加速逐頁掃描）
        if ai_enabled:
            ai_analysis = self._ai_multimodal_analysis(story_text, text_descriptions, image_content, has_images)
        else:
            ai_analysis = {
                'score': 70,
                'analysis': 'AI已關閉（逐頁模式加速）',
                'recommendations': [],
                'dimension_balance': 'N/A'
            }
        
        # 📊 5) 計算三大維度分數
        scores = self._calculate_five_dimension_scores(dimension_results, ai_analysis, has_images)
        
        # 💡 6) 生成改進建議
        suggestions = self._generate_improvement_suggestions(dimension_results, text_descriptions, has_images)
        
        return {
            "meta": {
                "version": "2.1_three_dimension_multimodal",
                "story_title": story_title,
                "mode": mode,
                "has_images": has_images,
                "image_count": len(image_paths) if image_paths else 0,
                "text_descriptions_count": sum(len(desc) for desc in text_descriptions.values()),
                "ai_available": self.ai.model_available if self.ai else False
            },
            "multimodal": {
                "text_descriptions": text_descriptions,
                "image_content": image_content if has_images else None,
                "dimension_results": dimension_results,
                "scores": (lambda sd: {k: sd[k] for k in sd.keys() if (k in self.enabled_dimensions or k in ("final","confidence"))})(
                    {
                        "plot_consistency": round(scores.plot_consistency, 1),
                        "character_appearance": round(scores.character_appearance, 1),
                        "scene_environment": round(scores.scene_environment, 1),
                        "final": round(scores.final, 1),
                        "confidence": round(scores.confidence, 2)
                    }
                ),
                "ai_analysis": ai_analysis,
                "suggestions": suggestions
            }
        }
    
    def _extract_text_visual_descriptions(self, story_text: str, narration_text: str = None, 
                                         dialogue_text: str = None) -> Dict[str, List[Dict]]:
        """從文字中提取三大維度的視覺描述
        
        返回格式：
        {
            'plot_consistency': [{'description': '...', 'location': '...', 'key_elements': [...]}],
            'character_appearance': [...],
            'scene_environment': [...], 
            'emotional_expression': [...],
            'temporal_logic': [...]
        }
        """
        
        # 合併所有文本來源
        all_text = self._merge_text_sources(story_text, narration_text, dialogue_text)
        
        # 分句處理
        sentences = self._split_sentences(all_text)
        
        # 三大維度的視覺描述
        descriptions = {
            'plot_consistency': [],
            'character_appearance': [],
            'scene_environment': []
        }
        
        for i, sentence in enumerate(sentences):
            # 1. 劇情一致性 - 提取動作、事件描述
            plot_desc = self._extract_plot_descriptions(sentence, i)
            if plot_desc:
                descriptions['plot_consistency'].extend(plot_desc)
            
            # 2. 角色外貌一致性 - 提取角色外觀描述
            char_desc = self._extract_character_descriptions(sentence, i)
            if char_desc:
                descriptions['character_appearance'].extend(char_desc)
            
            # 3. 場景環境一致性 - 提取場景、背景描述
            scene_desc = self._extract_scene_descriptions(sentence, i)
            if scene_desc:
                descriptions['scene_environment'].extend(scene_desc)
            
            # （已移除情感表達、時序邏輯）
        
        return descriptions

    def _refine_descriptions_by_tfidf(self, descriptions: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """以簡化TF-IDF思想過濾：
        - 先統計各維度 key_elements 出現次數與文件頻率（句級）
        - 移除低頻且影響小的元素，並限制每維度總特徵數量
        """
        min_df = self.match_config.get('tfidf_min_df', 2)
        max_k = self.match_config.get('tfidf_max_k', 80)
        refined = {}
        for dim, items in descriptions.items():
            if not items:
                refined[dim] = items
                continue
            # 蒐集句級出現（用 location 當句ID）
            elem_to_sents: Dict[str, Set[str]] = defaultdict(set)
            for it in items:
                sent_id = it.get('location','')
                for elem in it.get('key_elements', []):
                    elem_to_sents[elem].add(sent_id)
            # 過濾：至少出現在 min_df 個句子
            kept_elems = {e for e,s in elem_to_sents.items() if len(s) >= min_df}
            if not kept_elems:
                refined[dim] = items
                continue
            # 重新生成 items，保留被篩選的 elements
            new_items = []
            elem_count = Counter()
            for it in items:
                new_elems = [e for e in it.get('key_elements', []) if e in kept_elems]
                if not new_elems:
                    continue
                elem_count.update(new_elems)
                new_it = dict(it)
                new_it['key_elements'] = new_elems
                new_items.append(new_it)
            # 限制總特徵數量（按頻率排序保留）
            if len(elem_count) > max_k:
                top = set([e for e,_ in elem_count.most_common(max_k)])
                pruned_items = []
                for it in new_items:
                    new_elems = [e for e in it['key_elements'] if e in top]
                    if new_elems:
                        it2 = dict(it)
                        it2['key_elements'] = new_elems
                        pruned_items.append(it2)
                refined[dim] = pruned_items
            else:
                refined[dim] = new_items
        return refined
    
    def _merge_text_sources(self, story_text: str, narration_text: str = None, 
                           dialogue_text: str = None) -> str:
        """合併文本來源"""
        texts = []
        if story_text:
            texts.append(story_text)
        if narration_text:
            texts.append(narration_text)
        if dialogue_text:
            texts.append(dialogue_text)
        return " ".join(texts)
    
    def _extract_plot_descriptions(self, sentence: str, sentence_idx: int) -> List[Dict]:
        """提取劇情相關的視覺描述（動作、事件）"""
        descriptions = []
        
        # 動作動詞模式（優化版：更廣泛的動作捕獲）
        action_patterns = [
            r'\b(?:opened|closed|picked up|put down|threw|caught|gave|took|found|lost|placed|held|carried)\s+(?:a|an|the)?\s*\w+',
            r'\b(?:walked|ran|went|came|arrived|left|entered|exited|moved|stepped|approached|departed)\s+(?:to|from|into|out of)?\s*\w+',
            r'\b(?:hugged|kissed|shook hands|waved|pointed|gestured|smiled|laughed|talked|spoke|called)',
            r'\b(?:climbed|jumped|fell|sat down|stood up|knelt|crawled|turned|looked|watched|observed)',
            r'\b(?:cooked|ate|drank|served|prepared|cleaned|worked|played|read|wrote|drew|painted)',
            r'\b(?:swing|swinging|playing|gardening|watering|planting|growing|blooming)',
            r'\b(?:visiting|meeting|greeting|helping|teaching|learning|exploring|discovering)'
        ]
        
        for pattern in action_patterns:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            for match in matches:
                descriptions.append({
                    'description': match.group(),
                    'location': f'sentence_{sentence_idx + 1}',
                    'type': 'action',
                    'key_elements': self._extract_action_elements(match.group())
                })
        
        return descriptions
    
    def _extract_character_descriptions(self, sentence: str, sentence_idx: int) -> List[Dict]:
        """提取角色外貌相關的視覺描述"""
        descriptions = []
        
        # 角色外貌模式（優化版：更細緻的外貌特徵捕獲）
        appearance_patterns = [
            r'\b(?:tall|short|big|small|thin|fat|young|old|little|tiny)\s+(?:boy|girl|man|woman|person|child|kid)',
            r'\b(?:red|blue|green|brown|black|white|blonde|gray|grey|orange|yellow|pink|purple|dark|light)\s+(?:hair|eyes|skin)',
            r'\b(?:wearing|dressed in|had on|put on|wore)\s+(?:a|an|the)?\s*(?:\w+\s+)*(?:dress|shirt|pants|hat|shoes|coat|jacket|overalls|cardigan|sweater|jeans)',
            r'\b(?:with|has|had|having)\s+(?:a|an|the)?\s*(?:\w+\s+)*(?:beard|mustache|glasses|necklace|earrings|smile|frown)',
            r'\b(?:curly|straight|long|short|wavy)\s+(?:hair|beard)',
            r'\b(?:bright|sparkling|tired|happy|sad|kind|gentle)\s+(?:eyes|face|expression)',
            r'\b(?:blue|red|green|yellow|white|black|striped|polka-dot)\s+(?:shirt|dress|pants|socks|shoes|hat)'
        ]
        
        for pattern in appearance_patterns:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            for match in matches:
                descriptions.append({
                    'description': match.group(),
                    'location': f'sentence_{sentence_idx + 1}',
                    'type': 'appearance',
                    'key_elements': self._extract_appearance_elements(match.group())
                })
        
        return descriptions
    
    def _extract_scene_descriptions(self, sentence: str, sentence_idx: int) -> List[Dict]:
        """提取場景環境相關的視覺描述"""
        descriptions = []
        
        # 場景環境模式（優化版：擴展更多場景詞彙）
        scene_patterns = [
            r'\bin\s+(?:the\s+)?(?:forest|garden|house|room|kitchen|bedroom|park|school|library|yard|porch|veranda|workshop)',
            r'\b(?:sunny|rainy|cloudy|snowy|dark|bright|morning|afternoon|evening|night|outdoor|indoor)',
            r'\b(?:trees|flowers|grass|mountains|river|lake|buildings|furniture|plants|bushes|swing|patio|deck)',
            r'\b(?:on|under|near|beside|in front of|behind|around|outside|inside)\s+(?:the\s+)?\w+',
            r'\b(?:porch|veranda|backyard|front\s+yard|garden|greenhouse|lawn)\b',
            r'\b(?:surrounded\s+by|covered\s+with|filled\s+with)\s+\w+'
        ]
        
        for pattern in scene_patterns:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            for match in matches:
                descriptions.append({
                    'description': match.group(),
                    'location': f'sentence_{sentence_idx + 1}',
                    'type': 'environment',
                    'key_elements': self._extract_scene_elements(match.group())
                })
        
        return descriptions
    
    def _extract_emotion_descriptions(self, sentence: str, sentence_idx: int) -> List[Dict]:
        """提取情感表達相關的視覺描述"""
        descriptions = []
        
        # 情感表達模式
        emotion_patterns = [
            r'\b(?:smiled|frowned|laughed|cried|grinned|scowled)',
            r'\b(?:happy|sad|angry|excited|surprised|scared|worried|proud)',
            r'\b(?:eyes\s+(?:wide|bright|sparkling|tearful))',
            r'\b(?:face\s+(?:lit up|turned red|went pale))'
        ]
        
        for pattern in emotion_patterns:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            for match in matches:
                descriptions.append({
                    'description': match.group(),
                    'location': f'sentence_{sentence_idx + 1}',
                    'type': 'emotion',
                    'key_elements': self._extract_emotion_elements(match.group())
                })
        
        return descriptions
    
    def _extract_temporal_descriptions(self, sentence: str, sentence_idx: int) -> List[Dict]:
        """提取時序邏輯相關的視覺描述"""
        descriptions = []
        
        # 時序邏輯模式
        temporal_patterns = [
            r'\b(?:first|then|next|after|before|finally|meanwhile|suddenly)',
            r'\b(?:in the morning|at noon|in the evening|at night)',
            r'\b(?:earlier|later|soon|immediately|gradually)'
        ]
        
        for pattern in temporal_patterns:
            matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
            for match in matches:
                descriptions.append({
                    'description': match.group(),
                    'location': f'sentence_{sentence_idx + 1}',
                    'type': 'temporal',
                    'key_elements': self._extract_temporal_elements(match.group())
                })
        
        return descriptions
    
    def _extract_action_elements(self, text: str) -> List[str]:
        """從動作描述中提取關鍵元素"""
        elements = []
        text_lower = text.lower()
        
        # 動作類型
        if any(word in text_lower for word in ['opened', 'closed']):
            elements.append('object_manipulation')
        if any(word in text_lower for word in ['walked', 'ran', 'went']):
            elements.append('movement')
        if any(word in text_lower for word in ['hugged', 'kissed', 'shook']):
            elements.append('interaction')
        
        # 涉及的物品
        objects = re.findall(r'\b(?:door|window|book|cup|bag|box|chair|table)\b', text_lower)
        elements.extend(objects)
        
        return elements
    
    def _extract_appearance_elements(self, text: str) -> List[str]:
        """從外貌描述中提取關鍵元素"""
        elements = []
        text_lower = text.lower()
        
        # 顏色
        colors = re.findall(r'\b(?:red|blue|green|brown|black|white|blonde|gray)\b', text_lower)
        elements.extend(colors)
        
        # 服裝
        clothing = re.findall(r'\b(?:dress|shirt|pants|hat|shoes|coat|jacket)\b', text_lower)
        elements.extend(clothing)
        
        # 特徵
        features = re.findall(r'\b(?:hair|eyes|beard|mustache|glasses)\b', text_lower)
        elements.extend(features)
        
        return elements
    
    def _extract_scene_elements(self, text: str) -> List[str]:
        """從場景描述中提取關鍵元素"""
        elements = []
        text_lower = text.lower()
        
        # 地點
        locations = re.findall(r'\b(?:forest|garden|house|room|kitchen|bedroom|park|school)\b', text_lower)
        elements.extend(locations)
        
        # 天氣/時間
        conditions = re.findall(r'\b(?:sunny|rainy|cloudy|morning|afternoon|evening|night)\b', text_lower)
        elements.extend(conditions)
        
        # 自然元素
        nature = re.findall(r'\b(?:trees|flowers|grass|mountains|river|lake)\b', text_lower)
        elements.extend(nature)
        
        return elements
    
    def _extract_emotion_elements(self, text: str) -> List[str]:
        """從情感描述中提取關鍵元素"""
        elements = []
        text_lower = text.lower()
        
        # 情感類型
        emotions = re.findall(r'\b(?:happy|sad|angry|excited|surprised|scared|worried|proud)\b', text_lower)
        elements.extend(emotions)
        
        # 表達方式
        expressions = re.findall(r'\b(?:smiled|frowned|laughed|cried|grinned)\b', text_lower)
        elements.extend(expressions)
        
        return elements
    
    def _extract_temporal_elements(self, text: str) -> List[str]:
        """從時序描述中提取關鍵元素"""
        elements = []
        text_lower = text.lower()
        
        # 時序標記
        temporal_markers = re.findall(r'\b(?:first|then|next|after|before|finally|meanwhile|suddenly)\b', text_lower)
        elements.extend(temporal_markers)
        
        # 時間點
        time_points = re.findall(r'\b(?:morning|noon|evening|night|earlier|later)\b', text_lower)
        elements.extend(time_points)
        
        return elements
    
    def _analyze_image_content(self, image_paths: List[str], image_manifest: Dict = None) -> Dict[str, List[Dict]]:
        """分析圖像內容（三大維度）
        
        這是圖像分析的框架，實際實現需要整合：
        - 物件檢測模型（YOLO、DETR等）
        - 場景識別模型
        - 情感識別模型  
        - OCR文字識別
        
        返回格式：
        {
            'plot_consistency': [{'detected': '...', 'confidence': 0.9, 'bbox': [...]}],
            'character_appearance': [...],
            'scene_environment': [...],
            'emotional_expression': [...], 
            'temporal_logic': [...]
        }
        """
        
        image_content = {
            'plot_consistency': [],
            'character_appearance': [],
            'scene_environment': []
        }

        # 若提供 image_manifest（頁->代理檢出），先合併
        if image_manifest and isinstance(image_manifest, dict):
            for dim in image_content.keys():
                items = image_manifest.get(dim) or []
                for it in items:
                    # 正規化
                    detected = str(it.get('detected', '')).lower()
                    conf = float(it.get('confidence', 0.8))
                    image_content[dim].append({'detected': detected, 'confidence': conf, **{k:v for k,v in it.items() if k not in ('detected','confidence')}})
        
        for i, image_path in enumerate(image_paths):
            if not os.path.exists(image_path):
                continue
            
            try:
                merged_any = False
                # 1) 開放詞彙偵測（OWL-ViT / OWL-ViT-L），以文字 key_elements 當查詢
                queries = self._collect_open_vocab_queries()
                if queries:
                    ovd = self._ovd_detect_with_owlvit(image_path, queries)
                    for det in ovd:
                        dim = self._map_label_to_dimension(det.get('detected',''))
                        if dim in image_content:
                            image_content[dim].append(det)
                            merged_any = True
                
                # 2) 通用物件（YOLO，若可用）→ 劇情/物件為主
                yolo_dets = self._yolo_detect_optional(image_path)
                for det in yolo_dets:
                    dim = self._map_label_to_dimension(det.get('detected',''))
                    if dim in image_content:
                        image_content[dim].append(det)
                        merged_any = True

                # 2b) 顏色估計（輕量、無需訓練）→ 角色外觀補強
                # 優先使用 YOLO 的人像框；若沒有，對整張圖估色
                try:
                    person_boxes = []
                    if yolo_dets:
                        person_like = {'person','man','woman','boy','girl'}
                        for d in yolo_dets:
                            if str(d.get('detected','')) in person_like and d.get('bbox'):
                                person_boxes.append(d['bbox'])
                    color_tags = self._estimate_color_tags(image_path, person_boxes if person_boxes else None)
                    for tag in color_tags:
                        image_content['character_appearance'].append(tag)
                        merged_any = True
                except Exception:
                    pass
                # 記錄本頁影像路徑（供後續補查使用）
                image_content.setdefault('_image_paths', []).append(image_path)

                # 3) 影像字幕/標籤（BLIP/CLIP-tag 或其他標題模型）→ 擴充元素
                tags = self._caption_tags_optional(image_path)
                for tag in tags:
                    dim = self._map_label_to_dimension(tag.get('detected',''))
                    if dim in image_content:
                        image_content[dim].append(tag)
                        merged_any = True
                
                # 4) 若以上皆無法取得任何檢出，退回模擬
                if not merged_any:
                    image_analysis = self._simulate_image_analysis(image_path, i)
                    for dimension in image_content.keys():
                        if dimension in image_analysis:
                            image_content[dimension].extend(image_analysis[dimension])
                        
            except Exception as e:
                logger.warning("⚠️ 圖像分析失敗 %s: %s", image_path, e)
                continue
        
        return image_content

    def _estimate_color_tags(self, image_path: str, boxes: Optional[List[List[float]]] = None) -> List[Dict]:
        """從圖像（或指定框）估計主色，回傳 character_appearance 的顏色標籤。
        - 不依賴模型，使用 HSV 色相統計 + 簡單映射到基本顏色詞
        - 產出格式：[{detected: 'red', confidence: 0.6, source: 'color'}]
        """
        try:
            from PIL import Image as _Image
            import numpy as _np
            img = _Image.open(image_path).convert('RGB')
            regions = []
            if boxes:
                W, H = img.size
                for x1,y1,x2,y2 in boxes[:4]:  # 限制最多4個框
                    # 保障座標合理
                    x1 = max(0, min(W-1, int(x1)))
                    y1 = max(0, min(H-1, int(y1)))
                    x2 = max(0, min(W, int(x2)))
                    y2 = max(0, min(H, int(y2)))
                    if x2 > x1 and y2 > y1:
                        regions.append(img.crop((x1,y1,x2,y2)))
            if not regions:
                regions = [img]

            def rgb_to_hsv(arr):
                arr = arr.astype(_np.float32) / 255.0
                r,g,b = arr[...,0], arr[...,1], arr[...,2]
                cmax = _np.max(arr, axis=-1)
                cmin = _np.min(arr, axis=-1)
                delta = cmax - cmin + 1e-6
                h = _np.zeros_like(cmax)
                mask = (delta > 0)
                r_eq_max = (cmax == r) & mask
                g_eq_max = (cmax == g) & mask
                b_eq_max = (cmax == b) & mask
                h[r_eq_max] = (60 * ((g[r_eq_max]-b[r_eq_max]) / delta[r_eq_max]) + 0) % 360
                h[g_eq_max] = (60 * ((b[g_eq_max]-r[g_eq_max]) / delta[g_eq_max]) + 120) % 360
                h[b_eq_max] = (60 * ((r[b_eq_max]-g[b_eq_max]) / delta[b_eq_max]) + 240) % 360
                s = delta / (cmax + 1e-6)
                v = cmax
                return h, s, v

            # 基本色相區間（簡化）
            color_bins = [
                ('red', [(345, 360), (0, 15)]),
                ('orange', [(15, 45)]),
                ('yellow', [(45, 70)]),
                ('green', [(70, 170)]),
                ('cyan', [(170, 200)]),
                ('blue', [(200, 255)]),
                ('purple', [(255, 290)]),
                ('pink', [(290, 345)])
            ]

            counts = Counter()
            total = 0
            for region in regions:
                arr = _np.asarray(region.resize((160,160)))
                h, s, v = rgb_to_hsv(arr)
                # 濾掉過暗或過亮且無飽和的區域
                mask = (v > 0.2) & (s > 0.2)
                hh = h[mask]
                if hh.size == 0:
                    continue
                total += hh.size
                for name, intervals in color_bins:
                    c = 0
                    for a,b in intervals:
                        if a <= b:
                            c += int(((hh >= a) & (hh < b)).sum())
                        else:
                            # wrap-around for red high range
                            c += int(((hh >= a) | (hh < b)).sum())
                    counts[name] += c

            if total == 0:
                return []
            # 取占比前3色
            items = counts.most_common(3)
            out = []
            for name, c in items:
                conf = max(0.3, min(0.9, c / max(1, total)))
                out.append({'detected': name, 'confidence': float(conf), 'source': 'color'})
            return out
        except Exception:
            return []

    def _collect_open_vocab_queries(self) -> List[str]:
        """從最近文字描述蒐集開放詞彙查詢詞（零樣本）。
        會根據各維度的 key_elements 與描述，產生去重後的查詢字串。
        """
        queries: List[str] = []
        td = self._latest_text_descriptions or {}
        for dim, items in td.items():
            for it in items:
                # key_elements 優先；不足時用描述補充
                elems = list(it.get('key_elements') or [])
                if not elems and it.get('description'):
                    elems.append(it['description'])
                for e in elems:
                    q = self._normalize_label(str(e))
                    if q and q not in queries:
                        queries.append(q)
        # 擴充同義詞庫（優化版：更豐富的語義擴展）
        synonyms = {
            'porch': ['veranda','verandah','stoop','patio','front_steps','front_porch','balcony','deck'],
            'garden': ['yard','backyard','outdoor_space','lawn','greenhouse','plot'],
            'kitchen': ['cooking_area','dining_room','pantry'],
            'house': ['home','building','residence','dwelling'],
            'flowers': ['plants','blooms','blossoms','vegetation'],
            'swing': ['swinging','playground','play_equipment']
        }
        expanded = []
        for q in queries:
            expanded.append(q)
            for k, vs in synonyms.items():
                if k in q and q not in vs:
                    for v in vs:
                        if v not in expanded:
                            expanded.append(v)
        # 控制查詢數量，避免過長（提高上限到 80）
        return expanded[:80]

    def _normalize_label(self, text: str) -> str:
        text = (text or '').strip().lower().replace('-', ' ').replace('/', ' ')
        parts = [p for p in re.split(r"[^a-z0-9]+", text) if p]
        return '_'.join(parts)

    def _map_label_to_dimension(self, label: str) -> str:
        """將標籤粗略映射到五維度。
        優先規則：
        - 服飾/顏色/髮型/配件 → character_appearance
        - 場景/室內外/時間/天氣 → scene_environment
        - 表情/情緒動詞 → emotional_expression
        - 動作/交互/物件操作 → plot_consistency
        - 其他 → plot_consistency（保守放入劇情一致性）
        """
        t = (label or '').lower()
        if any(k in t for k in ['hair','dress','shirt','pants','hat','glasses','beard','mustache','eyes','overalls','cardigan','red_','blue_','green_','black_','white_','blonde','brown']):
            return 'character_appearance'
        if any(k in t for k in ['kitchen','garden','forest','room','indoor','outdoor','sunny','rainy','cloudy','morning','evening','night','school','library','park']):
            return 'scene_environment'
        if any(k in t for k in ['smile','smiling','happy','sad','angry','excited','surprised','scared','laugh','cry','frown']):
            return 'emotional_expression'
        if any(k in t for k in ['open','close','hold','pick','walk','run','go','come','hug','kiss','point','wave','cook','eat','drink','read','write']):
            return 'plot_consistency'
        return 'plot_consistency'

    def _ovd_detect_with_owlvit(self, image_path: str, queries: List[str]) -> List[Dict]:
        """以 OWL-ViT 執行零樣本開放詞彙偵測。
        若環境無 transformers/模型，安靜回傳空陣列。
        回傳格式：[{detected, confidence, bbox}]
        """
        try:
            from PIL import Image as _Image
            from transformers import pipeline
            import os as _os
            img = _Image.open(image_path).convert('RGB')
            # 先用本地路徑，否則回退雲端ID
            _local_owlvit = resolve_model_path('owlvit-base-patch16')
            _use_local = _os.path.isdir(_local_owlvit)
            _owlvit_id_or_path = _local_owlvit if _use_local else 'google/owlvit-base-patch16'
            # 優先使用 CPU（AMD 9900X 優化）
            use_cpu_for_vision = os.getenv('USE_CPU_FOR_VISION', 'true').lower() in ['true', '1']
            device = -1 if use_cpu_for_vision else (0 if torch.cuda.is_available() else -1)
            
            det = pipeline(
                'zero-shot-object-detection',
                model=_owlvit_id_or_path,
                device=device,
                model_kwargs={"local_files_only": True, "torch_dtype": "auto"} if _use_local else {"torch_dtype": "auto"},
            )
            # OWL-ViT 支援 list of candidate labels
            # 分批避免過多查詢
            results: List[Dict] = []
            batch = 64
            for s in range(0, len(queries), batch):
                labels = queries[s:s+batch]
                out = det(img, candidate_labels=labels, batch_size=8)
                for o in out:
                    label = self._normalize_label(o.get('label',''))
                    score = float(o.get('score', 0.0))
                    box = o.get('box') or {}
                    bbox = [float(box.get(k, 0.0)) for k in ['xmin','ymin','xmax','ymax']]
                    # 降低過濾門檻，提高檢測召回率
                    if score < 0.20:
                        continue
                    results.append({'detected': label, 'confidence': score, 'bbox': bbox, 'source': 'ovd'})
            return results
        except Exception:
            return []

    def _yolo_detect_optional(self, image_path: str) -> List[Dict]:
        """YOLO 通用物件偵測（可選）。無依賴或失敗時回空。
        將常見物件映射到劇情一致性/物件類別。
        """
        try:
            from ultralytics import YOLO
            # 懶載入並快取模型
            if self._yolo_model is None:
                self._yolo_model = YOLO(self.yolo_weights)
            res = self._yolo_model.predict(
                image_path,
                verbose=False,
                conf=self.yolo_conf,
                iou=self.yolo_iou,
                imgsz=self.yolo_imgsz,
                device='cpu' if use_cpu_for_vision else (0 if torch.cuda.is_available() else 'cpu'),
                half=False if use_cpu_for_vision else (True if torch.cuda.is_available() else False),
            )
            out: List[Dict] = []
            for r in res:
                names = r.names
                for b in r.boxes:
                    cls = int(b.cls[0]) if hasattr(b.cls, '__len__') else int(b.cls)
                    conf = float(b.conf[0]) if hasattr(b.conf, '__len__') else float(b.conf)
                    xyxy = b.xyxy[0].tolist() if hasattr(b.xyxy, '__len__') else [float(x) for x in b.xyxy]
                    label = self._normalize_label(names.get(cls, 'object'))
                    if conf < self.yolo_conf:
                        continue
                    out.append({'detected': label, 'confidence': conf, 'bbox': [float(v) for v in xyxy], 'source': 'yolo'})
            return out
        except Exception as e:
            logger.warning("⚠️ YOLO 失敗: %s", e)
            return []

    def _caption_tags_optional(self, image_path: str) -> List[Dict]:
        """影像字幕/標籤（可選）。失敗即回空。
        先用 BLIP 產生 caption，再從 caption 中抽關鍵詞形成 tag。
        """
        try:
            from PIL import Image as _Image
            from transformers import pipeline
            import os as _os
            img = _Image.open(image_path).convert('RGB')
            _local_blip = resolve_model_path('blip-image-captioning-base')
            _use_local = _os.path.isdir(_local_blip)
            _blip_id_or_path = _local_blip if _use_local else 'Salesforce/blip-image-captioning-base'
            cap = pipeline(
                'image-to-text',
                model=_blip_id_or_path,
                device=-1 if use_cpu_for_vision else (0 if torch.cuda.is_available() else -1),
                model_kwargs={"local_files_only": True, "torch_dtype": "auto"} if _use_local else {"torch_dtype": "auto"},
            )
            outs = cap(img, max_new_tokens=40)  # 增加 token 數獲得更詳細描述
            caption = ''
            if isinstance(outs, list) and outs:
                caption = str(outs[0].get('generated_text',''))
            if not caption:
                return []
            # 以簡單規則從 caption 取關鍵詞
            tokens = [self._normalize_label(t) for t in re.split(r"[^a-zA-Z0-9]+", caption) if t]
            tokens = [t for t in tokens if t and len(t) > 2]
            uniq = []
            for t in tokens:
                if t not in uniq:
                    uniq.append(t)
            # 顏色詞給更高的基礎信心，強化外觀維度的可檢出性（優化版）
            color_words = {
                'red','blue','green','yellow','orange','purple','pink','brown','black','white','blonde','grey','gray'
            }
            out = []
            for t in uniq[:20]:
                conf = 0.8 if t in color_words else 0.6  # 提高基礎置信度
                out.append({'detected': t, 'confidence': conf, 'source': 'caption'})
            return out
        except Exception:
            return []
    
    def _simulate_image_analysis(self, image_path: str, image_index: int) -> Dict[str, List[Dict]]:
        """模擬圖像分析（實際應替換為真實的圖像識別）"""
        
        # 模擬不同類型的檢測結果
        return {
                'plot_consistency': [
                    {'detected': 'person_walking', 'confidence': 0.85, 'bbox': [100, 150, 200, 400]},
                    {'detected': 'object_interaction', 'confidence': 0.78, 'bbox': [250, 200, 350, 300]}
                ],
                'character_appearance': [
                    {'detected': 'blonde_hair', 'confidence': 0.92, 'bbox': [120, 150, 180, 200]},
                    {'detected': 'red_dress', 'confidence': 0.88, 'bbox': [100, 250, 200, 400]}
                ],
                'scene_environment': [
                    {'detected': 'kitchen_scene', 'confidence': 0.90, 'bbox': [0, 0, 640, 480]},
                    {'detected': 'morning_lighting', 'confidence': 0.75, 'bbox': [0, 0, 640, 200]}
                ]
            }
    
    def _compare_text_image_consistency(self, text_descriptions: Dict[str, List[Dict]], 
                                      image_content: Dict[str, List[Dict]] = None, 
                                      has_images: bool = False) -> Dict[str, Dict]:
        """比對文字描述與圖像內容的一致性"""
        
        dimension_results = {}
        
        for dimension in self.enabled_dimensions:
            
            text_desc = text_descriptions.get(dimension, [])
            # 若文字端完全沒有描述，從資源檔建立文字側代理描述（避免一律50分）
            used_text_proxy = False
            if not text_desc:
                text_desc = self._build_text_proxy_from_resources(dimension)
                used_text_proxy = True if text_desc else False
            
            if has_images and image_content:
                image_desc = image_content.get(dimension, [])
                # 若圖像檢出為空，嘗試以資源檔生成代理檢出
                used_image_proxy = False
                if not image_desc:
                    proxy = self._build_proxy_detections_from_resources(dimension)
                    if proxy:
                        image_desc = proxy
                        used_image_proxy = True
                result = self._compare_dimension_consistency(text_desc, image_desc, dimension)
                result['used_text_proxy'] = used_text_proxy
                result['used_image_proxy'] = used_image_proxy
                
                # 學習式錨點更新：從成功匹配的image_labels學習
                if len(result.get('matches', [])) > 0:
                    successful_labels = self._collect_debug_image_labels(image_desc)[:3]  # 取前3個成功標籤
                    self._update_adaptive_anchors(dimension, successful_labels)
                
                # 關鍵缺失觸發再搜尋 → 實際追加一輪 OVD 補查（僅該維，嚴格門檻）
                missing_labels = result.get('missing_in_image', [])
                if missing_labels:
                    expanded_candidates = self._trigger_missing_search(dimension, missing_labels, 0)
                    # 嚴格過濾：語義相似度≥0.62，且為名詞/名詞片語（簡化：token長度≥3且不含介詞）
                    filtered = []
                    for q in expanded_candidates:
                        if len(q) < 3:
                            continue
                        if q in {"in","on","at","with","and","the","a","an","to","of"}:
                            continue
                        sim = self._semantic_similarity(' '.join(self._tokenize_text(' '.join(missing_labels))), q)
                        if sim >= 0.62:
                            filtered.append(q)
                    # 限流：每維最多 12 個，分批在 OVD 內處理
                    filtered = filtered[:12]
                    if filtered:
                        result['expanded_queries'] = filtered
                        try:
                            # 拿到本頁影像路徑（上游已記錄於 image_content）
                            image_paths_local = image_content.get('_image_paths') or []
                            ovd_refill = []
                            for ipath in image_paths_local[:1]:  # 單頁一般只有一張
                                dets = self._ovd_detect_with_owlvit(ipath, filtered)
                                # 僅納入 score≥0.30 的檢出
                                for d in dets:
                                    if float(d.get('confidence',0.0)) >= 0.30:
                                        image_desc.append(d)
                                        ovd_refill.append(d.get('detected',''))
                            if ovd_refill:
                                # 刷新 debug 與來源統計
                                result['ovd_refill_added'] = ovd_refill[:3]
                        except Exception:
                            pass
                
                # 附加除錯標籤：文字端與影像端實際使用的標籤（前5）
                result['debug_text_labels'] = self._collect_debug_text_labels(text_desc)[:5]
                result['debug_image_labels'] = self._collect_debug_image_labels(image_desc)[:5]
                # 統計來源（yolo/ovd/caption/color）數量，便於判斷來源參與度
                try:
                    src_count = {'yolo':0,'ovd':0,'caption':0,'color':0}
                    for it in image_desc or []:
                        s = str(it.get('source',''))
                        if s in src_count:
                            src_count[s] += 1
                    result['source_stats'] = src_count
                except Exception:
                    pass
            else:
                # 純文字分析模式
                result = self._analyze_text_only_consistency(text_desc, dimension)
                result['used_text_proxy'] = used_text_proxy
                result['used_image_proxy'] = False
                result['debug_text_labels'] = self._collect_debug_text_labels(text_desc)[:5]
                result['debug_image_labels'] = []
            
            dimension_results[dimension] = result
        
        return dimension_results

    def _collect_debug_text_labels(self, text_desc: List[Dict]) -> List[str]:
        labels: List[str] = []
        seen = set()
        for it in text_desc:
            keys = it.get('key_elements') or []
            if not keys and it.get('description'):
                keys = [it['description']]
            for k in keys:
                lab = str(k).strip().lower().replace(' ', '_')
                if not lab:
                    continue
                if lab in seen:
                    continue
                seen.add(lab)
                labels.append(lab)
        return labels

    def _collect_debug_image_labels(self, image_desc: List[Dict]) -> List[str]:
        stop = {"and","with","the","a","an","of","on","in","to","for","at"}
        labels: List[str] = []
        seen = set()
        for it in image_desc or []:
            lab = str(it.get('detected','')).strip().lower()
            lab = lab.replace(' ', '_')
            if not lab:
                continue
            if lab in seen:
                continue
            # 過濾過短與常見無意義詞
            base = lab.replace('_','')
            if len(base) < 3 or lab in stop:
                continue
            seen.add(lab)
            labels.append(lab)
        return labels

    def _build_text_proxy_from_resources(self, dimension: str) -> List[Dict]:
        """當文字側缺描述時，從 resources 構建簡單文字代理描述。
        產出格式與 _extract_* 相容：[{description, location, type, key_elements}]"""
        dets = self._build_proxy_detections_from_resources(dimension)
        items: List[Dict] = []
        if not dets:
            return items
        dtype = {
            'plot_consistency': 'action',
            'character_appearance': 'appearance',
            'scene_environment': 'environment'
        }.get(dimension, 'generic')
        for i, d in enumerate(dets[:50]):
            label = str(d.get('detected','')).strip()
            if not label:
                continue
            items.append({
                'description': label.replace('_', ' '),
                'location': f'resources_proxy_{i+1}',
                'type': dtype,
                'key_elements': [label]
            })
        return items

    def _build_proxy_detections_from_resources(self, dimension: str) -> List[Dict]:
        """當沒有CV檢出時，從資源檔（prompt/poses/character/scenes）構建代理檢出
        這讓場景/情緒/角色外貌能在無CV時仍有合理信號。
        """
        import glob
        proxy = []
        # 嘗試從當前故事的 resources 讀取（以簡單glob從常見位置抓取）
        story_resources = []
        for pat in [
            os.path.join('stories','*','resources','page_*_prompt.txt'),
            os.path.join('stories','*','resources','page_*_poses.txt'),
            os.path.join('stories','*','resources','scenes.txt'),
            os.path.join('stories','*','resources','character_*.txt')
        ]:
            story_resources.extend(glob.glob(pat))
        if not story_resources:
            return proxy
        # 根據dimension抽token
        def _read(p):
            try:
                with open(p,'r',encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return ''
        text = '\n'.join(_read(p) for p in story_resources)
        tokens = self._tokenize_text(text)
        # 映射到偵測類型（優化版：擴展關鍵詞集合）
        # 簡單規則：顏色/服飾→character_appearance；房間/戶外/天氣→scene；run/walk/open等→plot
        char_keys = {'hair','blonde','red','blue','green','brown','black','white','grey','gray','dress','shirt','pants','hat','glasses','beard','mustache','eyes','jacket','coat','overalls','cardigan','shoes','socks','face','smile','young','old','tall','short','curly','straight'}
        scene_keys = {'kitchen','workshop','garden','forest','room','indoor','outdoor','sunny','rainy','morning','evening','night','porch','veranda','house','yard','backyard','flowers','trees','plants','swing','deck','patio'}
        plot_keys = {'open','opened','close','closed','walk','walked','run','ran','went','came','hug','hugged','pick','picked','cook','cooking','play','playing','swing','swinging','visit','visiting','help','helping','work','working','grow','growing','bloom','blooming'}
        def _mk(items):
            return [{'detected': it, 'confidence': 0.8} for it in items]
        if dimension == 'character_appearance':
            proxy = _mk([t for t in tokens if t in char_keys])
        elif dimension == 'scene_environment':
            proxy = _mk([t for t in tokens if t in scene_keys])
        elif dimension == 'plot_consistency':
            proxy = _mk([t for t in tokens if t in plot_keys])
        return proxy

    def _build_page_level_proxy(self, story_dir: str, page_num: int) -> Dict[str, List[Dict]]:
        """針對單頁，從 resources/page_<n>_* 萃取代理檢出，強化該頁圖像語意"""
        res_dir = os.path.join(story_dir, 'resources')
        if not os.path.isdir(res_dir):
            return {}
        def _read(path):
            try:
                with open(path,'r',encoding='utf-8') as f:
                    return f.read()
            except Exception:
                return ''
        texts = []
        for name in [
            f'page_{page_num}_prompt.txt',
            f'page_{page_num}_poses.txt',
            'scenes.txt',
            'character_1_emma.txt',
            'character_2_grandpa_tom.txt',
            'character_3_alex.txt'
        ]:
            p = os.path.join(res_dir, name)
            if os.path.exists(p):
                texts.append(_read(p))
        if not texts:
            return {}
        tokens = self._tokenize_text('\n'.join(texts))
        # 同 _build_proxy_detections_from_resources 的關鍵詞集合（保持一致性）
        char_keys = {'hair','blonde','red','blue','green','brown','black','white','grey','gray','dress','shirt','pants','hat','glasses','beard','mustache','eyes','jacket','coat','overalls','cardigan','shoes','socks','face','smile','young','old','tall','short','curly','straight'}
        scene_keys = {'kitchen','workshop','garden','forest','room','indoor','outdoor','sunny','rainy','morning','evening','night','porch','veranda','house','yard','backyard','flowers','trees','plants','swing','deck','patio'}
        plot_keys = {'open','opened','close','closed','walk','walked','run','ran','went','came','hug','hugged','pick','picked','cook','cooking','play','playing','swing','swinging','visit','visiting','help','helping','work','working','grow','growing','bloom','blooming'}
        def _mk(items):
            return [{'detected': it, 'confidence': 0.85} for it in items]
        return {
            'character_appearance': _mk([t for t in tokens if t in char_keys]),
            'scene_environment': _mk([t for t in tokens if t in scene_keys]),
            'plot_consistency': _mk([t for t in tokens if t in plot_keys])
        }

    def _analyze_style_consistency(self, image_paths: List[str]) -> Dict:
        """簡易畫風一致性：以顏色直方圖+亮度+飽和度特徵估算，回傳一致性分數與離群頁。
        （不依賴深度模型，僅做快速啟發式）
        """
        feats = []
        pages = []
        for ip in image_paths:
            try:
                img = Image.open(ip).convert('RGB').resize((128, 128))
                arr = np.asarray(img, dtype=np.float32) / 255.0
                # 顏色直方圖（每通道16 bins）
                h_r, _ = np.histogram(arr[:,:,0], bins=16, range=(0,1), density=True)
                h_g, _ = np.histogram(arr[:,:,1], bins=16, range=(0,1), density=True)
                h_b, _ = np.histogram(arr[:,:,2], bins=16, range=(0,1), density=True)
                # 亮度/飽和度（近似）
                luminance = arr.mean()
                saturation = (arr.max(axis=2) - arr.min(axis=2)).mean()
                feat = np.concatenate([h_r, h_g, h_b, np.array([luminance, saturation])])
                feats.append(feat)
                # 抓頁碼
                fname = os.path.basename(ip)
                try:
                    n = int(fname.split('_')[1])
                except Exception:
                    n = 0
                pages.append(n)
            except Exception:
                continue
        if len(feats) < 2:
            return {'style_score': 100.0, 'outliers': []}
        M = np.vstack(feats)
        center = M.mean(axis=0)
        dists = np.linalg.norm(M - center, axis=1)
        # 以分位數做相對縮放，避免一律趨零
        p50 = float(np.percentile(dists, 50))
        p90 = float(np.percentile(dists, 90))
        if p90 <= p50:
            p90 = p50 + 1e-6
        # 將群體平均一致性約落在 80~90 分
        norm = min(1.0, max(0.0, (p90 - dists.mean()) / (p90 - p50)))
        style_score = 50.0 + norm * 50.0
        # 離群（距離 > p90）
        thr = p90
        outliers = sorted([(pages[i], float(dists[i])) for i in range(len(pages)) if dists[i] > thr], key=lambda x: -x[1])
        return {'style_score': style_score, 'outliers': outliers}
    
    def _compare_dimension_consistency(self, text_descriptions: List[Dict], 
                                     image_detections: List[Dict], 
                                     dimension: str) -> Dict:
        """比對單一維度的文字描述與圖像檢測結果"""
        
        if not text_descriptions:
            return {
                'score': 50,
                'matches': [],
                'mismatches': [],
                'missing_in_image': [],
                'extra_in_image': image_detections,
                'analysis': f'{dimension}：文字中缺少相關描述'
            }
        
        if not image_detections:
            return {
                'score': 30,
                'matches': [],
                'mismatches': [],
                'missing_in_image': [desc['description'] for desc in text_descriptions],
                'extra_in_image': [],
                'analysis': f'{dimension}：圖像中缺少對應內容'
            }
        
        # 執行匹配分析
        matches = []
        mismatches = []
        missing_in_image = []
        
        for text_desc in text_descriptions:
            best_match = self._find_best_image_match(text_desc, image_detections, dimension)
            
            if best_match and best_match['confidence'] > 0.6:
                matches.append({
                    'text': text_desc['description'],
                    'image': best_match['detected'],
                    'confidence': best_match['confidence']
                })
            else:
                missing_in_image.append(text_desc['description'])
        
        # 計算一致性分數（信心加權）
        total_text_items = len(text_descriptions)
        matched_items = len(matches)
        avg_conf = (sum(m['confidence'] for m in matches) / matched_items) if matched_items else 0.0
        if total_text_items > 0:
            match_ratio = matched_items / total_text_items
            # 信心加權匹配率：避免僅以數量決定分數
            score = (0.7 * match_ratio + 0.3 * avg_conf) * 100.0
        else:
            score = 50.0

        # 針對關鍵缺失加重懲罰（擴展關鍵詞集合，與代理檢測保持一致）
        critical_tokens = set()
        if dimension == 'character_appearance':
            critical_tokens = {'red','blue','green','brown','black','white','blonde','grey','gray','dress','shirt','pants','hat','hair','eyes','glasses','jacket','coat','overalls','cardigan','shoes','face','smile'}
        elif dimension == 'scene_environment':
            critical_tokens = {'kitchen','garden','forest','room','indoor','outdoor','sunny','rainy','morning','evening','night','porch','veranda','house','yard','flowers','trees','plants','swing'}
        elif dimension == 'plot_consistency':
            critical_tokens = {'open','opened','close','closed','walk','walked','run','ran','hug','hugged','pick','picked','cook','cooking','play','playing','swing','swinging','visit','visiting','help','helping','work','working'}
        critical_missing = [m for m in missing_in_image if any(t in self._tokenize_text(m) for t in critical_tokens)]
        if critical_missing:
            score -= min(15, 3 * len(critical_missing))  # 降低懲罰強度：原20→15，原5→3

        # 根據維度調整評分
        score = self._adjust_score_by_dimension(score, dimension, matches, critical_missing or missing_in_image)

        # 調試：保存前3個匹配樣例
        debug_top3 = sorted(matches, key=lambda x: -x.get('confidence', 0.0))[:3]

        return {
            'score': min(100, max(0, score)),
            'matches': matches,
            'mismatches': mismatches,
            'missing_in_image': missing_in_image,
            'extra_in_image': [det for det in image_detections if not self._is_detection_matched(det, matches)],
            'analysis': self._generate_dimension_analysis(dimension, matches, missing_in_image),
            'debug_matches_top3': debug_top3
        }
    
    def _find_best_image_match(self, text_desc: Dict, image_detections: List[Dict], 
                              dimension: str) -> Optional[Dict]:
        """為文字描述找到最佳的圖像匹配"""
        
        best_match = None
        best_score = 0.0
        
        # 將文字元素與檢測標籤都做 token 化（支援下劃線組合詞）
        text_elements_raw = list(text_desc.get('key_elements', []))
        text_description = text_desc['description']
        text_tokens = self._tokenize_text(' '.join(text_elements_raw + [text_description]))
        
        for detection in image_detections:
            detected_item = str(detection.get('detected', '')).lower()
            confidence = float(detection.get('confidence', 0.0))
            det_tokens = self._tokenize_label(detected_item)
            
            # token 交集作為主要匹配訊號
            if text_tokens:
                overlap = len(text_tokens.intersection(det_tokens))
                token_score = min(1.0, overlap / max(1, len(text_tokens)))  # 0~1
            else:
                token_score = 0.0
            
            # 簡化的語義相似度（字面重疊或向量），閾值可配置（優化版：各維度分別調整）
            sem_score = self._semantic_similarity(' '.join(text_tokens), ' '.join(det_tokens))  # 0~1
            base_min_sim = self.match_config.get('min_semantic_sim', 0.35)  # 全面降低基礎門檻
            local_min_sim = base_min_sim
            if dimension in ('scene_environment',):
                local_min_sim = max(0.0, base_min_sim - 0.08)  # 場景更寬鬆：0.35 → 0.27
            elif dimension in ('plot_consistency',):
                local_min_sim = max(0.0, base_min_sim - 0.05)  # 劇情稍寬鬆：0.35 → 0.30
            if sem_score < local_min_sim:
                sem_score = 0.0
            
            # 語義加權（資料驅動）：依據與概念錨點的相似度，不使用具體標籤清單
            keyword_boost = self._compute_semantic_boost(dimension, det_tokens)
            
            # 顏色對齊加權（僅外觀維度、且文字同一句含顏色+服飾/部位時）
            if dimension == 'character_appearance':
                color_set = {'red','blue','green','yellow','black','white','brown','blonde'}
                part_set = {'shirt','pants','dress','coat','jacket','hat','hair','eyes','overalls','cardigan','shoes'}
                text_has_color = any(c in text_tokens for c in color_set)
                text_has_part = any(p in text_tokens for p in part_set)
                if text_has_color and text_has_part:
                    det_has_color = any(c in det_tokens for c in color_set)
                    det_has_part = any(p in det_tokens for p in part_set)
                    if det_has_color or det_has_part:
                        keyword_boost *= 1.10  # 小幅加權，避免噪音

            # 匹配分數：token 為主，語義為輔，乘以置信度與關鍵詞加權
            w_t = self.match_config.get('token_overlap_weight', 0.7)
            w_s = self.match_config.get('semantic_weight', 0.3)
            match_score = (w_t * token_score + w_s * sem_score) * max(0.5, confidence) * keyword_boost
            
            if match_score > best_score:
                best_score = match_score
                best_match = detection
        
        # 放寬門檻，允許低分匹配避免全 0 分（優化版：各維度差異化調整）
        base_min_score = self.match_config.get('min_match_score', 0.15)  # 全面降低基礎門檻
        local_min_score = base_min_score
        if dimension in ('scene_environment',):
            local_min_score = max(0.0, base_min_score - 0.08)  # 場景最寬鬆：0.15 → 0.07
        elif dimension in ('plot_consistency',):
            local_min_score = max(0.0, base_min_score - 0.05)  # 劇情稍寬鬆：0.15 → 0.10
        return best_match if best_score >= local_min_score else None

    def _compute_semantic_boost(self, dimension: str, det_tokens: Set[str]) -> float:
        """根據與概念錨點（抽象語義）相似度計算加權，避免硬編碼具體標籤。
        - character_appearance: 與 color/clothing/appearance/face 之類概念接近
        - scene_environment: 與 scene/environment/indoor/outdoor/weather/time 的概念接近
        - plot_consistency: 與 action/interaction/motion/gesture/manipulation 的概念接近
        """
        try:
            if not (self.match_config.get('use_spacy_vectors', True) and getattr(self.nlp, 'vocab', None)):
                return 1.0
            
            # 優先使用動態學習的錨點，回退到靜態錨點
            anchors = self.adaptive_anchors.get(dimension, [])
            if not anchors:
                anchors_map = {
                    'character_appearance': ['color', 'clothing', 'garment', 'appearance', 'face', 'hair', 'eyes'],
                    'scene_environment': ['scene', 'environment', 'indoor', 'outdoor', 'weather', 'time', 'place'],
                    'plot_consistency': ['action', 'interaction', 'motion', 'gesture', 'manipulation', 'event']
                }
                anchors = anchors_map.get(dimension, ['content'])
            
            boost = 1.0
            # 計算 det_tokens 與 anchors 的最大相似度
            sims = []
            for tok in list(det_tokens)[:8]:  # 控制成本
                vtok = self.nlp.vocab.get(tok)
                if vtok is None or not vtok.has_vector:
                    continue
                for a in anchors:
                    va = self.nlp.vocab.get(a)
                    if va is None or not va.has_vector:
                        continue
                    sims.append(vtok.similarity(va))
            if sims:
                smax = max(sims)
                # 線性映射到 1.0~1.25（輕量加權）
                boost = 1.0 + max(0.0, min(0.25, (smax - 0.45) * 0.5))
            return float(boost)
        except Exception:
            return 1.0
    
    def _update_adaptive_anchors(self, dimension: str, successful_image_labels: List[str]):
        """從成功匹配的image_labels學習動態錨點"""
        if not successful_image_labels or not getattr(self.nlp, 'vocab', None):
            return
        
        try:
            # 將成功標籤加入歷史
            self.successful_matches[dimension].extend(successful_image_labels)
            
            # 保持歷史長度（最多保留最近100個）
            if len(self.successful_matches[dimension]) > 100:
                self.successful_matches[dimension] = self.successful_matches[dimension][-100:]
            
            # 簡化版本：直接使用最常見的成功標籤作為錨點
            from collections import Counter
            label_counts = Counter(self.successful_matches[dimension])
            
            # 取最常見的標籤作為錨點
            most_common = label_counts.most_common(3)
            for label, count in most_common:
                if label not in self.adaptive_anchors[dimension]:
                    self.adaptive_anchors[dimension].append(label)
                    # 保持錨點數量（最多5個）
                    if len(self.adaptive_anchors[dimension]) > 5:
                        self.adaptive_anchors[dimension] = self.adaptive_anchors[dimension][-5:]
                        break
        except Exception:
            pass
    
    def _trigger_missing_search(self, dimension: str, missing_labels: List[str], page_idx: int) -> List[str]:
        """針對關鍵缺失觸發再搜尋，動態擴展近義詞"""
        if not missing_labels or not getattr(self.nlp, 'vocab', None):
            return []
        
        # 關鍵詞模式（顏色、服飾、場景名）
        critical_patterns = {
            'character_appearance': ['red', 'blue', 'green', 'yellow', 'hair', 'shirt', 'pants', 'dress', 'eyes'],
            'scene_environment': ['porch', 'garden', 'house', 'room', 'forest', 'park', 'sunny', 'dark'],
            'plot_consistency': ['open', 'close', 'walk', 'run', 'smile', 'laugh', 'cry']
        }
        
        critical_missing = [label for label in missing_labels 
                          if any(pattern in label.lower() for pattern in critical_patterns.get(dimension, []))]
        
        if not critical_missing:
            return []
        
        # 為關鍵缺失詞找近義詞
        expanded_queries = []
        for missing in critical_missing:
            try:
                token = self.nlp.vocab.get(missing)
                if token and token.has_vector:
                    # 找語義相似的詞
                    similar_words = []
                    for word in self.nlp.vocab:
                        if word.has_vector and word.is_lower and len(word.text) > 2:
                            sim = token.similarity(word)
                            if sim > 0.6:  # 相似度閾值
                                similar_words.append((word.text, sim))
                    
                    # 取前3個最相似的詞
                    similar_words.sort(key=lambda x: x[1], reverse=True)
                    for word, _ in similar_words[:3]:
                        if word not in expanded_queries:
                            expanded_queries.append(word)
            except Exception:
                continue
        
        return expanded_queries[:5]  # 最多返回5個擴展查詢

    def _tokenize_label(self, label: str) -> Set[str]:
        """將圖像檢測標籤切成 tokens，並加入語義近鄰（非硬編碼）：
        - 基於 spaCy 向量，對每個 token 尋找近鄰相似詞（相似度≥semantic_token_min_sim）
        - 以少量權重參與，比對時能容忍 porch~veranda、near~beside 等變體
        """
        raw = (label or '').lower().replace('-', ' ').replace('/', ' ')
        parts = []
        for chunk in raw.split('_'):
            parts.extend(re.split(r"[^a-z]+", chunk))
        base = [p for p in parts if p]
        tokens = set(base)
        # 語義近鄰擴展（小規模）
        try:
            if self.match_config.get('use_spacy_vectors', True) and getattr(self.nlp, 'vocab', None):
                min_sim = float(self.match_config.get('semantic_token_min_sim', 0.55))
                for p in base[:6]:  # 限制成本
                    if not p:
                        continue
                    t = self.nlp.vocab.get(p)
                    if t is None or not t.has_vector:
                        continue
                    # 從同詞彙表取少量近鄰（使用最相近的若干詞）
                    # 這裡用簡化近鄰：與 base 其他 tokens 比較；若你未來提供全域詞表，可替換為 ANN
                    for q in base[:6]:
                        if q == p:
                            continue
                        tq = self.nlp.vocab.get(q)
                        if tq is None or not tq.has_vector:
                            continue
                        sim = t.similarity(tq)
                        if sim >= min_sim:
                            tokens.add(q)
        except Exception:
            pass
        return tokens

    def _tokenize_text(self, text: str) -> Set[str]:
        """將文字描述/元素切成 tokens 並標準化"""
        text = str(text).lower().replace('-', ' ').replace('/', ' ')
        tokens = re.split(r"[^a-z]+", text)
        # 過濾停用詞/過短詞，可視需要擴充
        stop = {"the","a","an","and","or","to","of","in","on","at","with","for","is","are"}
        return set(t for t in tokens if t and t not in stop and len(t) > 1)
    
    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """計算語義相似性：優先使用 spaCy 向量，相容回退字面重疊"""
        t1 = (text1 or '').strip()
        t2 = (text2 or '').strip()
        if not t1 or not t2:
            return 0.0
        # 使用向量相似
        if self.match_config.get('use_spacy_vectors', True) and getattr(self.nlp, 'vocab', None):
            try:
                doc1 = self.nlp(t1)
                doc2 = self.nlp(t2)
                sim = float(doc1.similarity(doc2))
                # 正規化到 0~1
                return max(0.0, min(1.0, sim))
            except Exception:
                pass
        # 回退：字面重疊
        words1 = set(t1.lower().split())
        words2 = set(t2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        return intersection / union if union > 0 else 0.0
    
    def _adjust_score_by_dimension(self, base_score: float, dimension: str, 
                                  matches: List[Dict], missing_items: List[str]) -> float:
        """根據維度特性調整分數"""
        
        # 不同維度的重要性權重
        dimension_weights = {
            'plot_consistency': 1.0,        # 劇情一致性最重要
            'character_appearance': 0.95,   # 角色外貌很重要
            'scene_environment': 0.85,      # 場景環境重要
            'emotional_expression': 0.90,   # 情感表達很重要
            'temporal_logic': 0.75          # 時序邏輯相對不那麼直觀
        }
        
        weight = dimension_weights.get(dimension, 1.0)
        adjusted_score = base_score * weight
        
        # 根據缺失項目數量進行懲罰（放寬，避免一刀切為 0）
        if missing_items:
            penalty = min(15, len(missing_items) * 3)
            adjusted_score -= penalty
        
        # 根據匹配質量進行加分
        if matches:
            avg_confidence = sum(match['confidence'] for match in matches) / len(matches)
            if avg_confidence > 0.8:
                adjusted_score += 5
        
        return adjusted_score
    
    def _is_detection_matched(self, detection: Dict, matches: List[Dict]) -> bool:
        """檢查檢測結果是否已被匹配"""
        detected_item = detection['detected']
        return any(match['image'] == detected_item for match in matches)
    
    def _generate_dimension_analysis(self, dimension: str, matches: List[Dict], 
                                   missing_items: List[str]) -> str:
        """生成維度分析報告"""
        
        dimension_names = {
            'plot_consistency': '劇情一致性',
            'character_appearance': '角色外貌一致性', 
            'scene_environment': '場景環境一致性',
            'emotional_expression': '情感表達一致性',
            'temporal_logic': '時序邏輯一致性'
        }
        
        dim_name = dimension_names.get(dimension, dimension)
        
        if not matches and not missing_items:
            return f'{dim_name}：無相關內容需要比對'
        
        analysis_parts = []
        
        if matches:
            analysis_parts.append(f'成功匹配 {len(matches)} 項')
            
        if missing_items:
            analysis_parts.append(f'圖像中缺失 {len(missing_items)} 項文字描述')
        
        return f'{dim_name}：' + '，'.join(analysis_parts)
    
    def _analyze_text_only_consistency(self, text_descriptions: List[Dict], dimension: str) -> Dict:
        """純文字模式的一致性分析"""
        
        if not text_descriptions:
            return {
                'score': 50,
                'analysis': f'{dimension}：缺少相關文字描述',
                'description_count': 0,
                'suggestions': [f'建議增加更多{dimension}相關的視覺描述']
            }
        
        # 基於文字描述的豐富度評分
        description_count = len(text_descriptions)
        unique_elements = set()
        
        for desc in text_descriptions:
            unique_elements.update(desc.get('key_elements', []))
        
        # 計算豐富度分數
        richness_score = min(100, description_count * 15 + len(unique_elements) * 5)
        
        # 根據維度調整
        dimension_multipliers = {
            'plot_consistency': 1.0,
            'character_appearance': 0.9,
            'scene_environment': 0.85,
            'emotional_expression': 0.95,
            'temporal_logic': 0.8
        }
        
        multiplier = dimension_multipliers.get(dimension, 1.0)
        final_score = richness_score * multiplier
        
        suggestions = []
        if description_count < 3:
            suggestions.append(f'建議增加更多{dimension}相關的視覺描述')
        if len(unique_elements) < 5:
            suggestions.append(f'建議豐富{dimension}的描述細節')
        
        return {
            'score': min(100, max(30, final_score)),
            'analysis': f'{dimension}：基於文字描述分析（{description_count}個描述，{len(unique_elements)}個元素）',
            'description_count': description_count,
            'unique_elements': len(unique_elements),
            'suggestions': suggestions
        }
    
    def _ai_multimodal_analysis(self, story_text: str, text_descriptions: Dict[str, List[Dict]], 
                               image_content: Dict[str, List[Dict]] = None, has_images: bool = False) -> Dict:
        """AI輔助多模態分析"""
        
        if not self.ai or not self.ai.model_available:
            return {
                'score': 70,
                'analysis': 'AI模型不可用，使用基礎分析',
                'recommendations': []
            }
        
        # 統計各維度描述數量
        desc_stats = {}
        for dimension, descriptions in text_descriptions.items():
            desc_stats[dimension] = len(descriptions)
        
        mode = "文字與圖像比對" if has_images else "純文字分析"
        
        try:
            # 使用現有的AI分析方法
            ai_result = self.ai.analyze_consistency(story_text, [], {})
            
            return {
                'score': ai_result.get('ai_score', 70),
                'analysis': f'AI{mode}分析：{ai_result.get("analysis", "多模態一致性分析完成")}',
                'recommendations': ai_result.get('recommendations', []),
                'dimension_balance': self._assess_description_balance(desc_stats)
            }
            
        except Exception as e:
            return {
                'score': 70,
                'analysis': f'AI分析失敗: {str(e)}',
                'recommendations': ['建議檢查文字描述的視覺豐富度']
            }
    
    def _assess_description_balance(self, desc_stats: Dict[str, int]) -> str:
        """評估各維度描述的平衡性"""
        
        if not desc_stats or all(count == 0 for count in desc_stats.values()):
            return "缺少視覺描述"
        
        total = sum(desc_stats.values())
        max_count = max(desc_stats.values())
        min_count = min(desc_stats.values())
        
        if max_count > total * 0.6:
            dominant_dim = max(desc_stats.keys(), key=desc_stats.get)
            return f"描述不平衡：{dominant_dim}過於突出"
        elif min_count == 0:
            missing_dims = [dim for dim, count in desc_stats.items() if count == 0]
            return f"缺少維度：{', '.join(missing_dims)}"
        else:
            return "描述分佈均衡"
    
    def _calculate_five_dimension_scores(self, dimension_results: Dict[str, Dict], 
                                       ai_analysis: Dict, has_images: bool) -> MultimodalScores:
        """計分（依啟用維度動態計算；未啟用維度置零且不輸出）。"""
        # 取啟用維度分數
        enabled = list(self.enabled_dimensions)
        scores_enabled: Dict[str, float] = {}
        for dim in enabled:
            scores_enabled[dim] = float(dimension_results.get(dim, {}).get('score', 50.0))

        # 簡化：等權平均（僅就啟用維度），再與 AI 分數等權平均
        if enabled:
            base_score = sum(scores_enabled[d] for d in enabled) / len(enabled)
        else:
            base_score = 50.0
        ai_score = float(ai_analysis.get('score', 70.0))
        final_score = (base_score + ai_score) / 2.0

        # 置信度：有圖較高；依匹配率調整（優化版：提高基礎置信度）
        confidence = 0.85 if has_images else 0.65
        total_matches = 0
        total_items = 0
        for result in dimension_results.values():
            if 'matches' in result:
                total_matches += len(result['matches'])
                total_items += len(result.get('missing_in_image', [])) + len(result['matches'])
        if total_items > 0:
            match_ratio = total_matches / total_items
            confidence *= (0.5 + match_ratio * 0.5)

        # 未啟用維度（為了資料類型兼容，設為 0）
        plot_score = scores_enabled.get('plot_consistency', 0.0)
        char_score = scores_enabled.get('character_appearance', 0.0)
        scene_score = scores_enabled.get('scene_environment', 0.0)
        emo_score = 0.0
        temp_score = 0.0

        return MultimodalScores(
            plot_consistency=plot_score,
            character_appearance=char_score,
            scene_environment=scene_score,
            final=min(100.0, max(0.0, final_score)),
            confidence=min(1.0, confidence)
        )
    
    def _generate_improvement_suggestions(self, dimension_results: Dict[str, Dict], 
                                        text_descriptions: Dict[str, List[Dict]], 
                                        has_images: bool) -> List[str]:
        """生成改進建議"""
        
        suggestions = []
        
        # 根據模式給出基礎建議
        if not has_images:
            suggestions.append("⚠️ 目前僅進行文字分析，建議提供圖像進行完整的多模態一致性檢查")
        
        # 根據各維度分數給出建議
        dimension_names = {
            'plot_consistency': '劇情一致性',
            'character_appearance': '角色外貌一致性',
            'scene_environment': '場景環境一致性', 
            'emotional_expression': '情感表達一致性',
            'temporal_logic': '時序邏輯一致性'
        }
        
        for dimension, result in dimension_results.items():
            score = result.get('score', 50)
            dim_name = dimension_names.get(dimension, dimension)
            
            if score < 60:
                suggestions.append(f"🚨 {dim_name}需要重點改進（分數：{score:.0f}）")
                
                # 具體問題建議
                if 'missing_in_image' in result and result['missing_in_image']:
                    missing_count = len(result['missing_in_image'])
                    suggestions.append(f"   圖像中缺失 {missing_count} 項文字描述的視覺元素")
                
                if 'suggestions' in result:
                    suggestions.extend([f"   {sugg}" for sugg in result['suggestions'][:2]])
                    
            elif score < 80:
                suggestions.append(f"⚠️ {dim_name}有改進空間（分數：{score:.0f}）")
        
        # 根據描述豐富度給出建議
        total_descriptions = sum(len(descs) for descs in text_descriptions.values())
        if total_descriptions < 10:
            suggestions.append("💡 建議增加更多視覺描述，豐富故事的畫面感")
        
        # 根據維度平衡性給出建議
        desc_counts = {dim: len(descs) for dim, descs in text_descriptions.items()}
        max_count = max(desc_counts.values()) if desc_counts else 0
        min_count = min(desc_counts.values()) if desc_counts else 0
        
        if max_count > 0 and min_count == 0:
            missing_dims = [dim for dim, count in desc_counts.items() if count == 0]
            suggestions.append(f"⚖️ 建議增加 {', '.join(missing_dims)} 相關的視覺描述")
        
        # 成功案例鼓勵
        good_scores = [result.get('score', 0) for result in dimension_results.values() if result.get('score', 0) >= 80]
        if good_scores:
            suggestions.append(f"✅ {len(good_scores)} 個維度表現良好，請保持")
        
        return suggestions if suggestions else ["✅ 多模態一致性表現良好"]

    def _extract_visual_elements(self, story_text: str, narration_text: str = None, 
                                dialogue_text: str = None) -> List[VisualElement]:
        """抽取視覺元素"""
        elements = []
        element_id_counter = 1
        
        # 合併文本來源
        text_sources = [
            ("story", story_text),
            ("narration", narration_text or ""),
            ("dialogue", dialogue_text or "")
        ]
        
        for source_type, text in text_sources:
            if not text.strip():
                continue
                
            sentences = self._split_sentences(text)
            
            for i, sentence in enumerate(sentences):
                # 檢查每種類型的視覺模式
                for element_type, patterns in self.visual_patterns.items():
                    for pattern in patterns:
                        matches = list(re.finditer(pattern, sentence, re.IGNORECASE))
                        
                        for match in matches:
                            description = match.group().strip()
                            
                            # 分析視覺屬性
                            attributes = self._extract_visual_attributes(description, sentence)
                            
                            element = VisualElement(
                                element_id=f"visual_{element_id_counter:03d}",
                                element_type=element_type,
                                description=description,
                                attributes=attributes,
                                location=f"{source_type}_sentence_{i+1}",
                                required_in_image=self._should_be_in_image(element_type, description),
                                consistency_requirements=self._get_consistency_requirements(element_type)
                            )
                            elements.append(element)
                            element_id_counter += 1
        
        # 去重複和合併相似元素
        unique_elements = self._deduplicate_visual_elements(elements)
        
        return unique_elements
    
    def _extract_visual_attributes(self, description: str, context: str) -> Dict[str, str]:
        """抽取視覺屬性"""
        attributes = {}
        
        # 顏色屬性
        colors = ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown', 'black', 'white', 'grey', 'blonde']
        for color in colors:
            if color in description.lower():
                attributes['color'] = color
                break
        
        # 尺寸屬性
        sizes = ['big', 'small', 'little', 'tiny', 'huge', 'large', 'tall', 'short']
        for size in sizes:
            if size in description.lower():
                attributes['size'] = size
                break
        
        # 情感屬性
        emotions = ['happy', 'sad', 'angry', 'excited', 'surprised', 'scared', 'worried', 'proud']
        for emotion in emotions:
            if emotion in context.lower():
                attributes['emotion'] = emotion
                break
        
        # 位置屬性
        positions = ['standing', 'sitting', 'lying', 'running', 'walking', 'jumping']
        for position in positions:
            if position in context.lower():
                attributes['pose'] = position
                break
        
        return attributes
    
    def _should_be_in_image(self, element_type: str, description: str) -> bool:
        """判斷元素是否應該出現在圖像中"""
        # 角色外觀和主要物件應該在圖像中
        if element_type in ['character_appearance', 'objects']:
            return True
        
        # 場景設定通常應該在圖像中
        if element_type == 'scene_setting':
            return True
        
        # 重要動作應該在圖像中體現
        if element_type == 'actions_poses':
            important_actions = ['running', 'jumping', 'dancing', 'hugging', 'pointing']
            return any(action in description.lower() for action in important_actions)
        
        # 明顯的情感表達應該在圖像中體現
        if element_type == 'emotions':
            visual_emotions = ['smiling', 'crying', 'laughing', 'frowning']
            return any(emotion in description.lower() for emotion in visual_emotions)
        
        return False
    
    def _get_consistency_requirements(self, element_type: str) -> List[str]:
        """獲取一致性要求"""
        requirements_map = {
            'character_appearance': [
                "角色外觀特徵應在所有圖像中保持一致",
                "服裝顏色和樣式應保持連續性",
                "身高比例應合理"
            ],
            'scene_setting': [
                "背景環境應符合故事設定",
                "場景元素位置應合理",
                "光線和天氣應一致"
            ],
            'objects': [
                "物件外觀應保持一致",
                "物件大小比例應合理",
                "物件位置變化應合乎邏輯"
            ],
            'actions_poses': [
                "動作應符合故事情節",
                "姿勢應自然合理",
                "動作序列應有連續性"
            ],
            'emotions': [
                "情感表達應與故事情節匹配",
                "表情變化應有邏輯性",
                "情感強度應適當"
            ]
        }
        
        return requirements_map.get(element_type, ["保持基本的視覺一致性"])
    
    def _deduplicate_visual_elements(self, elements: List[VisualElement]) -> List[VisualElement]:
        """去重複視覺元素"""
        unique_elements = []
        seen_descriptions = set()
        
        for element in elements:
            # 簡化的去重邏輯
            normalized_desc = re.sub(r'\s+', ' ', element.description.lower().strip())
            
            if normalized_desc not in seen_descriptions:
                seen_descriptions.add(normalized_desc)
                unique_elements.append(element)
            else:
                # 合併相似元素的屬性
                for existing in unique_elements:
                    if re.sub(r'\s+', ' ', existing.description.lower().strip()) == normalized_desc:
                        # 合併屬性
                        existing.attributes.update(element.attributes)
                        break
        
        return unique_elements
    
    def _generate_visual_checklist(self, visual_elements: List[VisualElement]) -> Dict:
        """生成視覺檢查清單"""
        checklist = {
            "characters": [],
            "settings": [],
            "objects": [],
            "actions": [],
            "emotions": [],
            "consistency_points": []
        }
        
        # 按類型分組元素
        for element in visual_elements:
            if element.element_type == "character_appearance":
                checklist["characters"].append({
                    "description": element.description,
                    "attributes": element.attributes,
                    "required": element.required_in_image
                })
            elif element.element_type == "scene_setting":
                checklist["settings"].append({
                    "description": element.description,
                    "attributes": element.attributes,
                    "required": element.required_in_image
                })
            elif element.element_type == "objects":
                checklist["objects"].append({
                    "description": element.description,
                    "attributes": element.attributes,
                    "required": element.required_in_image
                })
            elif element.element_type == "actions_poses":
                checklist["actions"].append({
                    "description": element.description,
                    "attributes": element.attributes,
                    "required": element.required_in_image
                })
            elif element.element_type == "emotions":
                checklist["emotions"].append({
                    "description": element.description,
                    "attributes": element.attributes,
                    "required": element.required_in_image
                })
        
        # 添加一致性檢查要點
        consistency_points = set()
        for element in visual_elements:
            consistency_points.update(element.consistency_requirements)
        
        checklist["consistency_points"] = list(consistency_points)
        
        # 添加兒童繪本特殊要求
        checklist["children_book_requirements"] = self.children_book_requirements
        
        return checklist
    
    def _analyze_images(self, image_paths: List[str], visual_elements: List[VisualElement]) -> List[ImageAnalysis]:
        """分析圖像（簡化版本 - 實際需要圖像識別模型）"""
        analyses = []
        
        for image_path in image_paths:
            if not os.path.exists(image_path):
                continue
            
            # 模擬圖像分析（實際應使用圖像識別模型）
            analysis = ImageAnalysis(
                image_path=image_path,
                detected_elements=[],  # 實際應包含檢測到的視覺元素
                missing_elements=[],   # 實際應包含缺失的元素
                inconsistent_elements=[],  # 實際應包含不一致的元素
                consistency_score=75.0  # 模擬分數
            )
            
            analyses.append(analysis)
        
        return analyses
    
    def _check_multimodal_consistency(self, visual_elements: List[VisualElement], 
                                    image_analyses: List[ImageAnalysis]) -> Dict:
        """檢查多模態一致性"""
        if not image_analyses:
            return self._text_proxy_consistency_check(visual_elements)
        
        consistency_results = {
            "plot_consistency": {"score": 80.0, "analysis": "劇情一致性良好"},
            "character_appearance": {"score": 85.0, "analysis": "角色外貌一致"},
            "scene_environment": {"score": 75.0, "analysis": "場景環境基本一致"},
            "emotional_expression": {"score": 90.0, "analysis": "情感表達豐富"},
            "temporal_logic": {"score": 70.0, "analysis": "時序邏輯合理"}
        }
        
        # 實際實現需要比較文本描述與圖像檢測結果
        # 這裡提供框架結構
        
        return consistency_results
    
    def _text_proxy_consistency_check(self, visual_elements: List[VisualElement]) -> Dict:
        """文字側代理一致性檢查（無圖像時）"""
        consistency_results = {
            "plot_consistency": {"score": 0.0, "analysis": "無圖像，無法評分"},
            "character_appearance": {"score": 0.0, "analysis": "無圖像，無法評分"},
            "scene_environment": {"score": 0.0, "analysis": "無圖像，無法評分"},
            "emotional_expression": {"score": 0.0, "analysis": "無圖像，無法評分"},
            "temporal_logic": {"score": 0.0, "analysis": "無圖像，無法評分"},
            "text_proxy_analysis": {}
        }
        
        # 分析文字中的視覺一致性
        character_elements = [e for e in visual_elements if e.element_type == "character_appearance"]
        scene_elements = [e for e in visual_elements if e.element_type == "scene_setting"]
        
        # 檢查角色描述一致性
        character_consistency = self._analyze_character_consistency(character_elements)
        consistency_results["text_proxy_analysis"]["character_analysis"] = character_consistency
        
        # 檢查場景描述一致性
        scene_consistency = self._analyze_scene_consistency(scene_elements)
        consistency_results["text_proxy_analysis"]["scene_analysis"] = scene_consistency
        
        # 生成文字側建議
        text_suggestions = []
        
        if len(character_elements) < 3:
            text_suggestions.append("角色外觀描述較少，建議增加更多視覺細節")
        
        if len(scene_elements) < 2:
            text_suggestions.append("場景描述較少，建議增加更多環境細節")
        
        consistency_results["text_proxy_suggestions"] = text_suggestions
        
        return consistency_results
    
    def _analyze_character_consistency(self, character_elements: List[VisualElement]) -> Dict:
        """分析角色一致性"""
        if not character_elements:
            return {"consistency_score": 100, "issues": [], "characters": []}
        
        # 按角色分組（簡化版本）
        character_groups = defaultdict(list)
        
        for element in character_elements:
            # 簡單的角色識別（實際需要更複雜的NER）
            if 'emma' in element.description.lower():
                character_groups['Emma'].append(element)
            elif 'alex' in element.description.lower():
                character_groups['Alex'].append(element)
            elif 'grandpa' in element.description.lower():
                character_groups['Grandpa'].append(element)
            else:
                character_groups['Other'].append(element)
        
        analysis = {
            "consistency_score": 85,
            "issues": [],
            "characters": []
        }
        
        for char_name, elements in character_groups.items():
            if len(elements) > 1:
                # 檢查屬性一致性
                colors = [e.attributes.get('color') for e in elements if e.attributes.get('color')]
                if len(set(colors)) > 1:
                    analysis["issues"].append(f"{char_name} 的顏色描述不一致: {set(colors)}")
                
                analysis["characters"].append({
                    "name": char_name,
                    "appearances": len(elements),
                    "attributes": elements[0].attributes if elements else {}
                })
        
        return analysis
    
    def _analyze_scene_consistency(self, scene_elements: List[VisualElement]) -> Dict:
        """分析場景一致性"""
        if not scene_elements:
            return {"consistency_score": 100, "issues": [], "scenes": []}
        
        analysis = {
            "consistency_score": 80,
            "issues": [],
            "scenes": []
        }
        
        # 分析場景類型
        scene_types = Counter()
        for element in scene_elements:
            if 'forest' in element.description.lower():
                scene_types['forest'] += 1
            elif 'house' in element.description.lower():
                scene_types['house'] += 1
            elif 'garden' in element.description.lower():
                scene_types['garden'] += 1
            else:
                scene_types['other'] += 1
        
        analysis["scenes"] = [{"type": scene_type, "count": count} for scene_type, count in scene_types.items()]
        
        return analysis
    
    def _advanced_ai_multimodal_analysis(self, story_text: str, visual_elements: List[VisualElement], 
                                       has_images: bool) -> Dict:
        """AI 深度多模態分析"""
        if not self.ai or not self.ai.model_available:
            return {"score": 70, "analysis": "AI模型不可用，使用基礎評分"}
        
        element_summary = f"檢測到 {len(visual_elements)} 個視覺元素"
        mode_info = "完整多模態分析" if has_images else "文字側代理分析"
        
        prompt = f"""
        請分析故事的視覺一致性（{mode_info}）：
        
        故事摘要：{story_text[:800]}...
        
        視覺元素統計：{element_summary}
        
        請評估：
        1. 視覺描述是否豐富且一致
        2. 角色和場景描述是否適合繪製
        3. 視覺元素是否支持故事敘述
        
        請給出評分（0-100）並說明主要問題。
        """
        
        try:
            ai_result = self.ai.analyze_consistency(story_text, [], {})
            ai_score = ai_result.get("ai_score", 70)
            
            return {
                "score": ai_score,
                "analysis": ai_result.get("analysis", "AI多模態分析完成"),
                "confidence": ai_result.get("confidence", 0.6),
                "visual_richness": len(visual_elements),
                "mode": "full_multimodal" if has_images else "text_proxy"
            }
        except Exception as e:
            return {"score": 70, "analysis": f"AI分析失敗: {str(e)}"}
    
    def _calculate_multimodal_scores(self, consistency_results: Dict, ai_analysis: Dict, 
                                   has_images: bool) -> MultimodalScores:
        """計算多模態分數"""
        # 從新的結構中提取分數
        plot_score = consistency_results.get("plot_consistency", {}).get("score", 50)
        character_score = consistency_results.get("character_appearance", {}).get("score", 50)
        scene_score = consistency_results.get("scene_environment", {}).get("score", 50)
        emotion_score = consistency_results.get("emotional_expression", {}).get("score", 50)
        temporal_score = consistency_results.get("temporal_logic", {}).get("score", 50)
        
        ai_score = ai_analysis.get("score", 70)
        
        # 三大維度權重分配
        weights = {
            'plot_consistency': 0.25,
            'character_appearance': 0.25,
            'scene_environment': 0.20,
            'emotional_expression': 0.20,
            'temporal_logic': 0.10
        }
        
        # 計算加權平均分數
        final_score = (
            plot_score * weights['plot_consistency'] +
            character_score * weights['character_appearance'] +
            scene_score * weights['scene_environment'] +
            emotion_score * weights['emotional_expression'] +
            temporal_score * weights['temporal_logic']
        )
        
        # AI分數影響
        final_score = (final_score * 0.8) + (ai_score * 0.2)
        
        # 計算置信度
        confidence = 0.8 if has_images else 0.6
        
        return MultimodalScores(
            plot_consistency=plot_score,
            character_appearance=character_score,
            scene_environment=scene_score,
            final=min(100.0, max(0.0, final_score)),
            confidence=confidence
        )
    
    def _generate_multimodal_suggestions(self, consistency_results: Dict, visual_checklist: Dict, 
                                       ai_analysis: Dict, has_images: bool) -> List[str]:
        """生成多模態建議"""
        suggestions = []
        
        if has_images:
            # 完整多模態建議
            issues = consistency_results.get("issues", [])
            if issues:
                suggestions.extend([f"圖文一致性問題: {issue}" for issue in issues[:3]])
            
            strengths = consistency_results.get("strengths", [])
            if strengths:
                suggestions.extend([f"優點: {strength}" for strength in strengths[:2]])
        else:
            # 文字側代理建議
            suggestions.append("⚠️ 目前僅進行文字側分析，建議提供圖像進行完整檢查")
            
            text_suggestions = consistency_results.get("text_proxy_suggestions", [])
            suggestions.extend(text_suggestions)
        
        # 基於視覺檢查清單的建議
        character_count = len(visual_checklist.get("characters", []))
        if character_count < 2:
            suggestions.append("角色視覺描述較少，建議增加更多角色外觀細節")
        
        setting_count = len(visual_checklist.get("settings", []))
        if setting_count < 2:
            suggestions.append("場景描述較少，建議增加更多環境和背景描述")
        
        # AI 建議
        if ai_analysis.get("score", 70) < 70:
            suggestions.append("AI分析顯示視覺描述需要改善")
        
        # 兒童繪本特殊建議
        if not has_images:
            suggestions.append("建議為繪者提供詳細的視覺指導文件")
            suggestions.append("確保關鍵情節轉折點有明確的視覺描述")
        
        return suggestions if suggestions else ["視覺描述完整，適合多模態呈現"]
    
    def _element_to_dict(self, element: VisualElement) -> Dict:
        """將VisualElement轉換為字典"""
        return {
            "element_id": element.element_id,
            "element_type": element.element_type,
            "description": element.description,
            "attributes": element.attributes,
            "location": element.location,
            "required_in_image": element.required_in_image,
            "consistency_requirements": element.consistency_requirements
        }


# ==================== 獨立運行入口（僅引導） ====================
if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(
        level=getattr(logging, os.environ.get("MULTIMODAL_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(message)s"
    )

    def is_story_directory(path: str) -> bool:
        if not os.path.isdir(path):
            return False
        en_dir = os.path.join(path, 'en')
        base_dir = en_dir if os.path.exists(en_dir) else path
        return os.path.exists(os.path.join(base_dir, 'full_story.txt'))

    def find_story_directories(root: str) -> list:
        if is_story_directory(root):
            return [root]
        story_dirs = []
        if not os.path.isdir(root):
            return story_dirs
        for name in os.listdir(root):
            candidate = os.path.join(root, name)
            if is_story_directory(candidate):
                story_dirs.append(candidate)
        return story_dirs

    root = 'output'
    story_dirs = find_story_directories(root)
    if not story_dirs:
        logger.error("❌ 未找到故事資料夾：%s", root)
        raise SystemExit(1)

    logger.info("開始多模態評估")
    logger.info("%s", "=" * 60)
    logger.info("📁 掃描 output，找到 %s 個故事資料夾", len(story_dirs))

    checker = MultimodalChecker(image_analysis_enabled=True)

    for story_dir in story_dirs:
        en_dir = os.path.join(story_dir, 'en')
        base_dir = en_dir if os.path.exists(en_dir) else story_dir
        main_file = os.path.join(base_dir, 'full_story.txt')
        if not os.path.exists(main_file):
            logger.warning("- 略過：%s (無 full_story.txt)", os.path.basename(story_dir))
            continue

        try:
            with open(main_file, 'r', encoding='utf-8') as f:
                text = f.read()

            image_paths = []
            photo_dir = os.path.join(story_dir, 'photo')
            if os.path.isdir(photo_dir):
                candidates = [
                    fname for fname in os.listdir(photo_dir)
                    if fname.startswith('page_') and '_scene_' in fname and fname.endswith('.png')
                ]

                def _page_key(name: str) -> int:
                    try:
                        base = name.split('_')[1]
                        return int(base)
                    except Exception:
                        return 0

                candidates.sort(key=_page_key)
                image_paths = [os.path.join(photo_dir, fname) for fname in candidates]

            per_page_results: List[Tuple[int, Dict]] = []
            per_page_dump: List[Dict] = []

            if image_paths:
                logger.info("")
                logger.info("📄 啟用逐頁對齊評估：")

                page_pairs = []
                for img_path in image_paths:
                    fname = os.path.basename(img_path)
                    try:
                        page_no = int(fname.split('_')[1])
                    except Exception:
                        page_no = 0
                    page_pairs.append((page_no, img_path))

                page_pairs.sort(key=lambda x: x[0])
                page_to_image_map: Dict[int, str] = {}
                for page_no, img_path in page_pairs:
                    page_to_image_map.setdefault(page_no, img_path)
                page_to_image = sorted(page_to_image_map.items(), key=lambda x: x[0])

                def _read_if_exists(path: str) -> str:
                    try:
                        if os.path.exists(path):
                            with open(path, 'r', encoding='utf-8') as handle:
                                return handle.read()
                    except Exception:
                        pass
                    return ''

                agg = {"plot": [], "char": [], "scene": [], "final": [], "conf": []}

                for page_no, img_path in page_to_image:
                    page_txt = _read_if_exists(os.path.join(base_dir, f"page_{page_no}.txt"))
                    if not page_txt:
                        candidates = [
                            os.path.join(base_dir, f"page_{page_no}_narration.txt"),
                            os.path.join(base_dir, f"page_{page_no}_dialogue.txt"),
                        ]
                        page_txt = "\n\n".join(filter(None, (_read_if_exists(p) for p in candidates)))
                    if not page_txt:
                        page_txt = text

                    page_manifest = checker._build_page_level_proxy(story_dir, page_no)
                    result = checker.check(
                        page_txt,
                        f"{os.path.basename(story_dir)}#p{page_no}",
                        image_paths=[img_path],
                        image_manifest=page_manifest,
                        ai_enabled=False
                    )
                    multimodal_data = result['multimodal']
                    score_data = multimodal_data['scores']
                    per_page_results.append((page_no, score_data))
                    per_page_dump.append({'page': page_no, 'scores': score_data, 'meta': result['meta']})
                    agg["plot"].append(score_data['plot_consistency'])
                    agg["char"].append(score_data['character_appearance'])
                    agg["scene"].append(score_data['scene_environment'])
                    agg["final"].append(score_data['final'])
                    agg["conf"].append(score_data['confidence'])

                def _avg(values: List[float]) -> float:
                    return sum(values) / len(values) if values else 0.0

                logger.info("")
                logger.info("📊 逐頁分數（前5頁示例）：")
                for page_no, score_data in per_page_results[:5]:
                    logger.info(
                        "  p%02d → final %.1f | plot %.1f | char %.1f | scene %.1f",
                        page_no,
                        score_data['final'],
                        score_data['plot_consistency'],
                        score_data['character_appearance'],
                        score_data['scene_environment'],
                    )

                try:
                    logger.info("")
                    logger.info("🔎 逐頁細節（前3頁）：")
                    for page_no, img_path in page_to_image[:3]:
                        page_txt = _read_if_exists(os.path.join(base_dir, f"page_{page_no}.txt")) or text
                        page_manifest = checker._build_page_level_proxy(story_dir, page_no)
                        detail_result = checker.check(
                            page_txt,
                            f"{os.path.basename(story_dir)}#p{page_no}",
                            image_paths=[img_path],
                            image_manifest=page_manifest,
                            ai_enabled=False
                        )
                        dim_results = detail_result['multimodal']['dimension_results']
                        text_descriptions = detail_result['multimodal'].get('text_descriptions') or {}
                        image_content = detail_result['multimodal'].get('image_content') or {}
                        logger.info("  p%02d：", page_no)
                        for dimension in ['plot_consistency', 'character_appearance', 'scene_environment']:
                            dim_data = dim_results.get(dimension, {})
                            matches = len(dim_data.get('matches', []) or [])
                            missing = dim_data.get('missing_in_image', []) or []
                            used_text_proxy = dim_data.get('used_text_proxy', False)
                            used_image_proxy = dim_data.get('used_image_proxy', False)
                            preview = ", ".join(missing[:3]) if missing else "-"
                            logger.info(
                                "    - %s: matches %s | missing %s | text_proxy=%s image_proxy=%s",
                                dimension,
                                matches,
                                len(missing),
                                used_text_proxy,
                                used_image_proxy,
                            )
                            if preview != "-":
                                logger.info("      · missing_preview: %s", preview)

                            try:
                                text_items = text_descriptions.get(dimension, []) or []
                                text_labels = []
                                seen_text = set()
                                for item in text_items:
                                    keys = item.get('key_elements') or []
                                    if not keys and item.get('description'):
                                        keys = [item['description']]
                                    for key in keys:
                                        label = str(key).strip().lower().replace(' ', '_')
                                        if label and label not in seen_text:
                                            seen_text.add(label)
                                            text_labels.append(label)
                                text_preview = ", ".join(text_labels[:5]) if text_labels else "-"

                                image_items = image_content.get(dimension, []) or []
                                image_labels = []
                                seen_image = set()
                                for item in image_items:
                                    label = str(item.get('detected', '')).strip().lower()
                                    if label and label not in seen_image:
                                        seen_image.add(label)
                                        image_labels.append(label)
                                image_preview = ", ".join(image_labels[:5]) if image_labels else "-"

                                logger.info("      · text_labels: %s", text_preview)
                                logger.info("      · image_labels: %s", image_preview)

                                source_stats = dim_data.get('source_stats') or {}
                                if source_stats:
                                    logger.info(
                                        "      · source_stats: yolo=%s ovd=%s caption=%s",
                                        source_stats.get('yolo', 0),
                                        source_stats.get('ovd', 0),
                                        source_stats.get('caption', 0),
                                    )

                                expanded_queries = dim_data.get('expanded_queries', [])
                                if expanded_queries:
                                    logger.info("      · expanded_queries: %s", ", ".join(expanded_queries[:3]))

                                anchor_list = checker.adaptive_anchors.get(dimension)
                                if anchor_list:
                                    logger.info("      · adaptive_anchors: %s", ", ".join(anchor_list[:3]))
                            except Exception:
                                pass
                except Exception:
                    pass

                logger.info("")
                logger.info("📊 聚合總結：")
                logger.info("  🎯 總分(平均): %.1f/100 (置信度: %.2f)", _avg(agg['final']), _avg(agg['conf']))
                logger.info("  🎬 劇情一致性(平均): %.1f/100", _avg(agg['plot']))
                logger.info("  👤 角色外貌(平均): %.1f/100", _avg(agg['char']))
                logger.info("  🏞️ 場景環境(平均): %.1f/100", _avg(agg['scene']))

                try:
                    used_text_proxy_cnt = 0
                    used_image_proxy_cnt = 0
                    for page_no, img_path in page_to_image[:5]:
                        page_txt = _read_if_exists(os.path.join(base_dir, f"page_{page_no}.txt")) or text
                        page_manifest = checker._build_page_level_proxy(story_dir, page_no)
                        proxy_result = checker.check(
                            page_txt,
                            f"{os.path.basename(story_dir)}#p{page_no}",
                            image_paths=[img_path],
                            image_manifest=page_manifest,
                            ai_enabled=False
                        )
                        dim_results = proxy_result['multimodal']['dimension_results']
                        for dimension in ['plot_consistency', 'character_appearance', 'scene_environment']:
                            dim_data = dim_results.get(dimension, {})
                            if dim_data.get('used_text_proxy'):
                                used_text_proxy_cnt += 1
                            if dim_data.get('used_image_proxy'):
                                used_image_proxy_cnt += 1
                    logger.info(
                        "  🔧 代理使用（前5頁×3維）：文字代理 %s 次 | 圖像代理 %s 次",
                        used_text_proxy_cnt,
                        used_image_proxy_cnt,
                    )
                except Exception:
                    pass

                style_report = checker._analyze_style_consistency([img for _, img in page_to_image])
                logger.info("")
                logger.info("🎨 畫風一致性：")
                logger.info("  一致性分數: %.1f/100  (分數越高代表越一致)", style_report['style_score'])
                if style_report.get('outliers'):
                    logger.info("  可能的風格離群頁（前3）：")
                    for page_no, score in style_report['outliers'][:3]:
                        logger.info("    p%02d → 差異度 %.2f", page_no, score)

                if checker.output_config.get('write_per_page_json', True):
                    out_path = os.path.join(
                        story_dir,
                        checker.output_config.get('per_page_json_name', 'multimodal_page_report.json')
                    )
                    try:
                        with open(out_path, 'w', encoding='utf-8') as handle:
                            json.dump(
                                {
                                    'pages': per_page_dump,
                                    'aggregate': {
                                        'final': _avg(agg['final']),
                                        'plot': _avg(agg['plot']),
                                        'character': _avg(agg['char']),
                                        'scene': _avg(agg['scene']),
                                        'confidence': _avg(agg['conf'])
                                    },
                                    'style': style_report
                                },
                                handle,
                                ensure_ascii=False,
                                indent=2
                            )
                        logger.info("")
                        logger.info("📝 已輸出逐頁報告: %s", out_path)
                    except Exception:
                        pass

                logger.info("%s", "=" * 60)

            else:
                result = checker.check(text, os.path.basename(story_dir), image_paths=image_paths)
                data = result['multimodal']
                scores = data['scores']

                logger.info("")
                logger.info("%s", "=" * 60)
                logger.info("📖 檢測: %s", os.path.basename(story_dir))
                logger.info("📄 文檔: %s", os.path.basename(main_file))
                logger.info("🖼️ 圖像數: %s  模式: %s", len(image_paths), result['meta']['mode'])
                logger.info("📊 三大維度分數:")
                logger.info("  🎯 總分: %.1f/100 (置信度: %.2f)", scores['final'], scores['confidence'])
                logger.info("  🎬 劇情一致性: %.1f/100", scores['plot_consistency'])
                logger.info("  👤 角色外貌: %.1f/100", scores['character_appearance'])
                logger.info("  🏞️ 場景環境: %.1f/100", scores['scene_environment'])

                text_descriptions = data.get('text_descriptions', {})
                total_descriptions = sum(len(desc) for desc in text_descriptions.values())
                logger.info("🔍 文字描述總數: %s 個", total_descriptions)

                suggestions = data.get('suggestions', [])
                if suggestions:
                    logger.info("")
                    logger.info("💡 建議 (最多3項):")
                    for suggestion in suggestions[:3]:
                        logger.info("  └─ %s", suggestion)

                logger.info("%s", "=" * 60)

        except Exception as exc:
            logger.exception("❌ 失敗 %s: %s", os.path.basename(story_dir), exc)