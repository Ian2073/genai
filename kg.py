"""
故事生成知識圖譜 (Knowledge Graph)
負責管理故事類別、主題、分支原型等配置資訊
"""

import json
import re
import random
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# =============================================================================
# 分支原型定義 (Branch Archetypes)
# 為不同年齡層設計的互動選擇類型，包含感官指引、情緒軌跡等
# =============================================================================

BRANCH_ARCHETYPES = {
    # --- 身體動作導向 (2-5 歲重點) ---
    "brave": {
        "label": "Brave Choice",
        "desc": "Face the challenge directly with courage.",
        "keywords": ["brave", "bold", "protect", "face", "courage", "stand tall"],
        "suitable_ages": ["all"],
        "sensory_guide": "Focus on physical sensations of strength (heartbeat, firm stance) or loud/strong sounds.",
        "emotional_arc": "From Fear/Hesitation to Courage/Pride.",
        "resolution_model": "Overcoming the obstacle through direct confrontation or endurance."
    },
    "energetic": {
        "label": "Action Choice",
        "desc": "Use speed, jumping, or physical activity.",
        "keywords": ["run", "jump", "speed", "fast", "climb", "zoom"],
        "suitable_ages": ["age_2_3", "age_4_5", "age_6_8"],
        "sensory_guide": "Focus on the wind in hair, muscle movement, impulse, specific verbs (whoosh, thump).",
        "emotional_arc": "From Restless/Eager to Satisfied/Exhausted.",
        "resolution_model": "Outrunning or physically bypassing the problem."
    },
    "sensory": {
        "label": "Touch/Feel Choice",
        "desc": "Solve by touching, holding, or physically interacting closely.",
        "keywords": ["touch", "hold", "soft", "texture", "feel", "squeeze"],
        "suitable_ages": ["age_2_3", "age_4_5"],
        "sensory_guide": "Intense focus on texture (rough, smooth, sticky), temperature, and tactile feedback.",
        "emotional_arc": "From Unknown to Familiarity/Comfort.",
        "resolution_model": "Understanding the object/creature by physically connecting with it."
    },

    # --- 腦力與問題解決 (4-8 歲重點) ---
    "smart": {
        "label": "Smart Choice",
        "desc": "Use a clever idea, tool, or plan.",
        "keywords": ["think", "idea", "plan", "solve", "smart", "tool"],
        "suitable_ages": ["age_4_5", "age_6_8", "age_9_10"],
        "sensory_guide": "Visual focus on details, patterns, or looking at specific parts of an object.",
        "emotional_arc": "From Confusion/Puzzlement to Clarity/Achievement.",
        "resolution_model": "Using an object or information to unlock the solution."
    },
    "curious": {
        "label": "Curious Choice",
        "desc": "Investigate to find out 'why' or 'what'.",
        "keywords": ["look", "explore", "ask", "search", "wonder", "why"],
        "suitable_ages": ["all"],
        "sensory_guide": "Visual sparkles, light, hidden corners; Sounds of rustling or whispering.",
        "emotional_arc": "From Wonder/Mystery to Discovery/Awe.",
        "resolution_model": "Finding hidden information or a secret path."
    },
    "creative": {
        "label": "Creative Choice",
        "desc": "Use imagination, art, or 'pretend' magic.",
        "keywords": ["pretend", "make", "paint", "draw", "imagine", "magic"],
        "suitable_ages": ["all"],
        "sensory_guide": "Vivid colors, imaginary sounds, transformation of ordinary objects.",
        "emotional_arc": "From Boredom/Stuck to Inspiration/Wonder.",
        "resolution_model": "Transforming the problem into something else (e.g., turning a monster into a balloon)."
    },

    # --- 社交與情感 (2-8 歲核心) ---
    "kind": {
        "label": "Kind Choice",
        "desc": "Offer help, share, or show empathy.",
        "keywords": ["help", "share", "gentle", "kind", "friend", "hug"],
        "suitable_ages": ["all"],
        "sensory_guide": "Warmth, gentle voice, soft touch, smiling faces.",
        "emotional_arc": "From Others' Sadness to Shared Joy/Connection.",
        "resolution_model": "Healing or fixing the problem through emotional connection/sharing."
    },
    "teamwork": {
        "label": "Team Choice",
        "desc": "Ask a friend or family member for help.",
        "keywords": ["together", "ask", "team", "family", "help", "hand in hand"],
        "suitable_ages": ["all"],
        "sensory_guide": "Hearing multiple voices, holding hands, coordinated movement.",
        "emotional_arc": "From Overwhelmed/Alone to Supported/Safe.",
        "resolution_model": "Pooling resources or strength to move something too heavy for one."
    },
    "diplomatic": {
        "label": "Talking Choice",
        "desc": "Use words to ask nicely or explain.",
        "keywords": ["ask", "say", "words", "talk", "listen", "please"],
        "suitable_ages": ["age_2_3", "age_4_5", "age_6_8"],
        "sensory_guide": "Focus on voice tone (soft, clear), eye contact, listening.",
        "emotional_arc": "From Tension/Misunderstanding to Agreement/Peace.",
        "resolution_model": "Persuasion or negotiation (using 'Please' and 'Thank you')."
    },
    "funny": {
        "label": "Funny Choice",
        "desc": "Do something silly to diffuse tension.",
        "keywords": ["laugh", "silly", "joke", "funny", "play", "giggle"],
        "suitable_ages": ["all"],
        "sensory_guide": "Laughter sounds, funny faces, wobbly movements, tickles.",
        "emotional_arc": "From Tension/Scary to Joy/Relief.",
        "resolution_model": "Making the obstacle seem less scary by mocking it or distracting it."
    },

    # --- 品格與價值觀 (4-8 歲) ---
    "cautious": {
        "label": "Careful Choice",
        "desc": "Take a safe, slow, or patient path.",
        "keywords": ["careful", "slow", "wait", "safe", "watch", "patient"],
        "suitable_ages": ["all"],
        "sensory_guide": "Quietness, stillness, observing small details while waiting.",
        "emotional_arc": "From Anxiety/Haste to Relief/Security.",
        "resolution_model": "Avoiding the danger entirely or waiting for it to satisfy pass."
    },
    "honest": {
        "label": "Honest Choice",
        "desc": "Tell the truth or admit a mistake.",
        "keywords": ["truth", "sorry", "admit", "honest", "tell", "promise"],
        "suitable_ages": ["age_4_5", "age_6_8", "age_9_10"],
        "sensory_guide": "Clear voice, standing straight, looking in eyes.",
        "emotional_arc": "From Guilt/Heavy Heart to Lightness/Pride.",
        "resolution_model": "Solving a misunderstanding by revealing the truth."
    },
    "nature": {
        "label": "Nature Choice",
        "desc": "Connect with an animal, plant, or environment.",
        "keywords": ["animal", "plant", "listen", "nature", "gentle", "grow"],
        "suitable_ages": ["all"],
        "sensory_guide": "Smell of earth/rain, animal sounds (chirp, purr), texture of leaves/fur.",
        "emotional_arc": "From Restless/Disconnected to Calm/Harmony.",
        "resolution_model": "Following an animal guide or using a natural element (vine, rock)."
    },
    "musical": {
        "label": "Musical Choice",
        "desc": "Use song, rhythm, or humming to solve or calm.",
        "keywords": ["sing", "song", "hum", "rhythm", "music", "dance"],
        "suitable_ages": ["age_2_3", "age_4_5", "age_6_8"],
        "sensory_guide": "Melody, rhythm patterns (clap-clap), harmony, vibration.",
        "emotional_arc": "From Discord/Noise to Harmony/Peace.",
        "resolution_model": "Soothing a creature with song or matching a pattern to open a door."
    },
    "imaginative": {
        "label": "Dream Choice",
        "desc": "Use a dream-like logic or wish.",
        "keywords": ["wish", "dream", "hope", "star", "believe"],
        "suitable_ages": ["age_2_3", "age_4_5"],
        "sensory_guide": "Soft light, clouds, whispers, floating sensation.",
        "emotional_arc": "From Hopelessness to Magic/Possibility.",
        "resolution_model": "A wish comes true or the environment responds to the child's belief."
    }
}


def _format_label(identifier: Optional[str]) -> str:
    if not identifier:
        return "General"
    return identifier.replace("_", " ").title()

# =============================================================================
# 核心數據結構 (Core Data Structures)
# =============================================================================

class NodeType(Enum):
    AGE_GROUP = "age_group"
    CATEGORY = "category"
    SUBCATEGORY = "subcategory"
    THEME = "theme"
    CHARACTER = "character"
    SCENE = "scene"
    CONCEPT = "concept"
    STORY_STATE = "story_state"
    GENERATION_PARAM = "generation_param"
    EMOTION = "emotion"
    LEARNING_OBJECTIVE = "learning_objective"
    PACING_ELEMENT = "pacing_element"
    CHARACTER_ARC = "character_arc"
    CULTURAL_ELEMENT = "cultural_element"
    VISUAL_STYLE = "visual_style"
    RELATIONSHIP = "relationship"

@dataclass
class KGNode:
    id: str
    type: NodeType
    label: str
    properties: Dict[str, Any]
    
@dataclass
class KGEdge:
    source: str
    target: str
    relation: str
    properties: Dict[str, Any] = None

# =============================================================================
# 主類別 (Main Class)
# =============================================================================

class StoryGenerationKG:
    """故事生成專用知識圖譜"""

    KG_SCHEMA_VERSION = "StoryGenerationKG-1.1"
    
    # 故事生成系統的核心假設 (System Core Assumptions)
    SYSTEM_CORE_ASSUMPTIONS = (
        "This system is a story-driven interactive narrative, not a game or instructional tool. "
        "Most pages are lightweight narrative pages (60–100 words). "
        "Transitional pages are allowed and do not need explicit functions. "
        "Each story contains only one designed turning point, where interaction may occur. "
        "Interaction exists only at the turning point and affects subsequent pages. "
        "Turning point pages may be longer (120–160 words). "
        "Interaction must be embedded as natural in-story actions, never as explicit choices or UI prompts. "
        "Interaction results must not provide immediate feedback, scores, or evaluative praise. "
        "Consequences unfold gradually through subsequent narrative events and character responses. "
        "Branches represent value-oriented action paths expressed through action → experience → reflection, "
        "never through labels or moral judgments. "
        "Page count is fixed by age group: Age 4–5: 8 pages, Age 6–7: 9 pages, Age 2–3: legacy linear. "
        "Educational meaning remains implicit, revealed only through story consequences."
    )

    # 關係 schema (domain/range)：讓 KG 更像可檢驗的 ontology，而非鬆散資料結構。
    # None 代表允許多種 target type（需在 validate 中特例處理）。
    RELATION_SCHEMA: Dict[str, Tuple[Optional[NodeType], Optional[NodeType]]] = {
        # Core relations
        "suitable_for": (NodeType.AGE_GROUP, None),  # AGE_GROUP -> (CATEGORY|THEME)
        "contains_theme": (NodeType.CATEGORY, NodeType.THEME),
        "appears_in": (NodeType.CHARACTER, NodeType.CATEGORY),
        "has_character": (NodeType.CATEGORY, NodeType.CHARACTER),
        "has_subcategory": (NodeType.CATEGORY, NodeType.SUBCATEGORY),
        "supports_theme": (NodeType.SUBCATEGORY, NodeType.THEME),
        "covers_concept": (NodeType.SUBCATEGORY, NodeType.CONCEPT),
        "suggests_scene": (NodeType.THEME, NodeType.SCENE),
        "involves_concept": (NodeType.THEME, NodeType.CONCEPT),
        # Variation semantic links
        "structure_suitable_for": (NodeType.GENERATION_PARAM, NodeType.CATEGORY),
        "catalyst_fits_category": (NodeType.GENERATION_PARAM, NodeType.CATEGORY),
        "dynamic_suitable_for_age": (NodeType.GENERATION_PARAM, NodeType.AGE_GROUP),
        # Emotion relations
        "teaches_emotion": (NodeType.THEME, NodeType.EMOTION),
        "appropriate_emotion_for_age": (NodeType.AGE_GROUP, NodeType.EMOTION),
        "character_expresses": (NodeType.CHARACTER, NodeType.EMOTION),
        # Learning objective relations
        "teaches_objective": (NodeType.THEME, NodeType.LEARNING_OBJECTIVE),
        "achievable_at_age": (NodeType.LEARNING_OBJECTIVE, NodeType.AGE_GROUP),
        # Pacing relations
        "uses_pacing": (NodeType.THEME, NodeType.PACING_ELEMENT),
        "pacing_fits_age": (NodeType.PACING_ELEMENT, NodeType.AGE_GROUP),
        # Character arc relations
        "supports_arc": (NodeType.THEME, NodeType.CHARACTER_ARC),
        "character_can_experience": (NodeType.CHARACTER, NodeType.CHARACTER_ARC),
        # Cultural element relations
        "involves_cultural_element": (NodeType.THEME, NodeType.CULTURAL_ELEMENT),
        "cultural_age_appropriate": (NodeType.CULTURAL_ELEMENT, NodeType.AGE_GROUP),
        # Visual style relations
        "preferred_style": (NodeType.CATEGORY, NodeType.VISUAL_STYLE),
        "age_appropriate_style": (NodeType.AGE_GROUP, NodeType.VISUAL_STYLE),
        "scene_requires_style": (NodeType.SCENE, NodeType.VISUAL_STYLE),
        # Character relationship
        "related_to": (NodeType.CHARACTER, NodeType.CHARACTER),
    }
    
    def __init__(self):
        self.nodes = {}  # id -> KGNode
        self.edges = []  # List[KGEdge]
        self.nx_graph = nx.DiGraph()  # NetworkX圖，用於可視化
        
        # 故事生成過程中的臨時狀態
        self.generation_states = {}
        
        # 初始化基礎數據
        self._initialize_base_data()
        
        # 自動執行一次推理以豐富圖譜連接
        self.infer_relations()

    def _get_rng(self, rng: Optional[random.Random] = None) -> random.Random:
        return rng if isinstance(rng, random.Random) else random.Random()
    
    # =============================================================================
    # 1. 初始化與數據加載 (Initialization & Data Loading)
    # =============================================================================

    def _initialize_base_data(self):
        """初始化基礎知識數據"""
        
        # 年齡組節點 - 增強版本，包含詳細的用字和品質要求
        age_groups = [
            ("age_2_3", "Age 2-3", {
                "min_age": 2, "max_age": 3,
                "word_limit": (30, 50), "page_range": (4, 4),
                "complexity": "very_simple",
                "language_guidelines": "Use simple, repetitive words. Avoid complex grammar. Focus on basic actions and emotions.",
                "dialogue_rules": "Each character speaks in one tiny sentence (≤8 words) using toddler-friendly words and soft sound effects.",
                "narration_rules": "Retell the page in toddler-friendly spoken English with playful sound effects and gentle pauses.",
                "visual_style": "Soft board-book watercolor style with big friendly shapes, pastel backgrounds, and consistent outfits.",
                "layout_config": {
                    "total_pages": 4,
                    "turning_point_page": 0,
                    "branch_count": 0,
                    "structure": "linear",
                    "description": "Linear 4-page (no interaction)"
                },
                "word_ranges": {
                    "narrative": (50, 80),
                    "turning_point": (50, 80),
                    "post_branch": (50, 80)
                },
                "interaction_rules": {
                    "has_interaction": False,
                    "turning_point_only": False,
                    "description": "No interaction for age 2-3"
                },
                "layout_templates": [
                    {
                        "id": "linear_4", "total": 4, "decision_page": 0, "branch_count": 0, 
                        "desc": "Fixed Linear 4-page"
                    }
                ],
                "vocabulary_level": "basic_concrete",
                "sentence_structure": "simple_subject_verb",
                "character_naming": {
                    "rules": "Keep names very simple and consistent",
                    "examples": ["Emma", "Grandpa Tom", "Alex"],
                    "avoid": ["complex compound names", "spelling variations", "nicknames"]
                },
                "grammar_requirements": {
                    "sentence_length": "3-10 words per sentence", # [ADJUST] Relaxed for natural flow
                    "punctuation": "proper spacing after periods, commas, exclamation marks",
                    "article_usage": "use 'a' before consonants, 'an' before vowels",
                    "contractions": "use proper apostrophes (don't, can't, won't)",
                    "word_spacing": "NEVER join words together - always separate with spaces",
                    "character_consistency": "ALWAYS use exact same names (Little Emma, Grandpa Tom, Little Alex)",
                    "avoid": ["word concatenation", "incomplete contractions", "inconsistent character names"]
                },
                "content_consistency": {
                    "character_behavior": "predictable and simple",
                    "plot_structure": "linear and repetitive", 
                    "theme_focus": "single clear message",
                    "page_format": "ONLY use 'Page X:' format - no variations",
                    "text_quality": "proper spacing between all words"
                }
            }),
            ("age_4_5", "Age 4-5", {
                "min_age": 4, "max_age": 5,
                "word_limit": (40, 70), "page_range": (14, 18),
                "complexity": "basic",
                "language_guidelines": "Use clear, simple language with some descriptive words. Maintain consistent character names.",
                "dialogue_rules": "Each line should be one short sentence (≤12 words) with clear feelings, playful sounds, and no long speeches.",
                "narration_rules": "Paraphrase the scene in warm read-aloud English using short conversational sentences and simple transitions.",
                "visual_style": "Hand-painted picture-book style with warm pastels, gentle lighting, and consistent character proportions.",
                "layout_config": {
                    "total_pages": 8,
                    "turning_point_page": 4,
                    "turning_point_range": [3, 5],
                    "turning_point_suggestion": {
                        "conflict_stories": 3,
                        "exploration_stories": 4,
                        "relationship_stories": 4,
                        "adventure_stories": 3,
                        "default": 4
                    },
                    "branch_count": 2,
                    "structure": "single_turning_point",
                    "description": "Fixed 8-page with flexible turning point (P3-P5)",
                    "page_structure": {
                        "P1-P2": "setup and context",
                        "P3-P5": "turning point zone (interaction)",
                        "P6-P7": "post-branch narrative",
                        "P8": "ending/reflection"
                    }
                },
                "word_ranges": {
                    "narrative": (60, 100),
                    "turning_point": (120, 160),
                    "post_branch": (100, 140)
                },
                "interaction_rules": {
                    "has_interaction": True,
                    "turning_point_only": True,
                    "max_interactions": 1,
                    "description": "Only P4 has interaction, embedded as natural story action"
                },
                "layout_templates": [
                    {
                        "id": "std_16", "total": 16, "decision_page": 8, "branch_count": 2, 
                        "desc": "Standard Fixed 16-page (Decision @ Page 8)"
                    }
                ],
                "vocabulary_level": "basic_descriptive",
                "sentence_structure": "simple_with_adjectives",
                "character_naming": {
                    "rules": "EXACT character names - no variations allowed",
                    "examples": ["Emma", "Grandpa Tom", "Alex"],
                    "required_format": "Title Case with spaces (Emma NOT emma)",
                    "avoid": ["name variations", "spelling inconsistencies", "joined names", "different titles"]
                },
                "grammar_requirements": {
                    "sentence_length": "5-15 words maximum", # [ADJUST] Relaxed to allow better flow
                    "punctuation": "periods, exclamation marks, simple questions",
                    "article_usage": "proper 'a' and 'an' usage required",
                    "verb_tenses": "simple present and past only",
                    "word_spacing": "NEVER join words - always separate with spaces",
                    "contractions": "use proper apostrophes (don't, can't, won't)",
                    "avoid": ["word concatenation", "incomplete contractions", "encoding errors"]
                },
                "content_consistency": {
                    "character_behavior": "consistent personality traits",
                    "plot_structure": "clear beginning, middle, end",
                    "theme_focus": "one main theme with supporting elements",
                    "page_format": "ONLY use 'Page X:' format - no variations",
                    "text_quality": "proper spacing between all words, consistent character names"
                }
            }),
            ("age_6_8", "Age 6-8", {
                "min_age": 6, "max_age": 8,
                "word_limit": (50, 100), "page_range": (18, 22),
                "complexity": "intermediate",
                "language_guidelines": "Use varied vocabulary with proper grammar. Ensure character name consistency and logical plot flow.",
                "dialogue_rules": "Use 1-2 short sentences per character (≤18 words) with lively verbs and expressive reactions.",
                "narration_rules": "Rephrase the events in energetic spoken English with rhythm, natural pauses, and occasional sound cues.",
                "visual_style": "Cohesive storybook style with cinematic framing, soft rim lighting, and expressive character poses.",
                "layout_config": {
                    "total_pages": 9,
                    "turning_point_page": 5,
                    "turning_point_range": [4, 6],
                    "turning_point_suggestion": {
                        "conflict_stories": 5,
                        "exploration_stories": 5,
                        "relationship_stories": 4,
                        "adventure_stories": 5,
                        "mystery_stories": 5,
                        "default": 5
                    },
                    "branch_count": 2,
                    "structure": "single_turning_point",
                    "description": "Fixed 9-page with interaction at P5 (Trunk P1-P4, Branch P6-P7, Ending P8-P9)",
                    "branch_span_pages": 2,
                    "ending_span_pages": 2,
                    "converge_ending": True,
                    "page_structure": {
                        "P1-P4": "shared trunk (setup)",
                        "P5": "turning point (interaction)",
                        "P6-P7": "distinct branch experience (consequences)",
                        "P8-P9": "converging ending (resolution)"
                    }
                },
                "word_ranges": {
                    "narrative": (60, 100),
                    "turning_point": (120, 160),
                    "post_branch": (100, 140)
                },
                "interaction_rules": {
                    "has_interaction": True,
                    "turning_point_only": True,
                    "max_interactions": 1,
                    "description": "Only P5 has interaction, embedded as natural story action"
                },
                "layout_templates": [
                    {
                        "id": "std_20", "total": 20, "decision_page": 10, "branch_count": 3, 
                        "desc": "Standard Fixed 20-page (Decision @ Page 10)"
                    }
                ],
                "vocabulary_level": "intermediate_expressive",
                "sentence_structure": "varied_simple_compound",
                "character_naming": {
                    "rules": "Exact name consistency required across all pages",
                    "examples": ["Emma", "Grandpa Tom", "Alex"],
                    "required_format": "Exact same format every time (Emma, Grandpa Tom, Alex)",
                    "avoid": ["any spelling variations", "informal nicknames", "inconsistent titles", "word concatenation"]
                },
                "grammar_requirements": {
                    "sentence_length": "8-16 words recommended",
                    "punctuation": "full range except complex punctuation", 
                    "grammar_check": "subject-verb agreement, proper tenses",
                    "spelling": "accuracy required for all words",
                    "word_spacing": "MANDATORY spaces between all words",
                    "contractions": "proper apostrophes required (don't, can't, won't)",
                    "avoid": ["joined words", "missing spaces", "encoding errors", "character name variations"]
                },
                "content_consistency": {
                    "character_development": "logical character growth",
                    "plot_coherence": "events must connect logically",
                    "theme_integration": "theme woven throughout story",
                    "page_format": "STRICT format: 'Page X:' only",
                    "text_quality": "perfect character name consistency, proper word spacing"
                }
            }),
            # TEMPORARILY DISABLED: Age 9-10 configuration
            # ("age_9_10", "Age 9-10", {
            #     "min_age": 9, "max_age": 10,
            #     "word_limit": (60, 120), "page_range": (18, 24),
            #     "complexity": "advanced",
            #     "language_guidelines": "Use sophisticated vocabulary with complex sentence structures. Maintain strict consistency in all story elements.",
            #     "dialogue_rules": "Keep dialogue snappy (≤20 words per turn) with expressive yet concise wording and purposeful banter.",
            #     "narration_rules": "Deliver lively spoken narration with clear pacing, rhetorical questions, and dramatic emphasis.",
            #     "visual_style": "Detailed illustrated novel style with rich color harmony, cinematic depth, and consistent character silhouettes.",
            #     "layout_templates": [
            #         {
            #             "id": "adv_20", "total": 20, "decision_page": 10, "branch_count": 3, 
            #             "desc": "Advanced Fixed 20-page (Decision @ Page 10)"
            #         }
            #     ],
            #     "vocabulary_level": "advanced_nuanced",
            #     "sentence_structure": "complex_varied_sophisticated",
            #     "character_naming": {
            #         "rules": "Precise character naming with no variations allowed",
            #         "examples": ["Emma", "Grandpa Tom", "Alex"],
            #         "avoid": ["any name inconsistencies", "spelling errors", "character confusion"]
            #     },
            #     "grammar_requirements": {
            #         "sentence_length": "10-20 words with variety",
            #         "punctuation": "full punctuation range including dialogue",
            #         "grammar_check": "advanced grammar rules, complex tenses",
            #         "style": "varied sentence beginnings and structures"
            #     },
            #     "content_consistency": {
            #         "character_arcs": "sophisticated character development",
            #         "plot_complexity": "multiple connected story elements",
            #         "theme_depth": "nuanced theme exploration"
            #     }
            # })  # END age_9_10 (DISABLED)
        ]
        
        for node_id, label, props in age_groups:
            self.add_node(node_id, NodeType.AGE_GROUP, label, props)
        
        # 故事類別節點 - 完整配置系統
        categories = [
            ("educational", "Educational", {
                "focus": "learning_and_discovery",
                "approach": "interactive_hands_on", 
                "subcategories": {
                    "moral": {
                        "themes": ["sharing", "friendship", "courage", "honesty"],
                        "focus": "teaching moral values and character development",
                        "key_elements": ["moral_teaching", "character_growth", "ethical_decision", "positive_behavior", "value_demonstration"],
                        "story_variations": {
                            "situations": [
                                "finding a lost toy at the playground",
                                "deciding whether to share their favorite snack",
                                "helping a friend who is feeling sad",
                                "telling the truth about breaking something",
                                "including a new child in their games"
                            ],
                            "challenges": [
                                "choosing between personal wants and helping others",
                                "standing up for what's right even when it's difficult",
                                "learning to apologize and make things right",
                                "showing kindness to someone who was unkind first",
                                "being patient when things don't go as planned"
                            ]
                        }
                    },
                    "knowledge": {
                        "themes": ["animals", "nature", "science", "numbers", "letters"],
                        "focus": "providing factual knowledge and curiosity about the world",
                        "key_elements": ["educational_content", "discovery_process", "learning_method", "knowledge_application", "understanding_check"],
                        "layered_variations": {
                            "knowledge_domains": [
                                "Amazing animals and their behaviors",
                                "Plants and how they grow",
                                "Simple science and how things work",
                                "Numbers, counting, and patterns",
                                "Letters, words, and storytelling",
                                "Weather, seasons, and nature cycles",
                                "Space, planets, and the universe",
                                "Ocean life and water environments",
                                "Human body and staying healthy",
                                "Transportation and how things move"
                            ],
                            "exploration_approaches": [
                                "through hands-on experiments and observations",
                                "by discovering patterns and connections in nature",
                                "through asking questions and finding surprising answers",
                                "by comparing different examples and learning differences",
                                "through creative projects that demonstrate learning",
                                "by connecting new knowledge to everyday life"
                            ],
                            "learning_activities": [
                                "interactive games and puzzles",
                                "creative arts and crafts projects",
                                "outdoor exploration and observation",
                                "simple experiments and demonstrations",
                                "storytelling and imaginative play",
                                "building and creating together",
                                "songs, rhymes, and movement activities",
                                "books, pictures, and visual learning"
                            ]
                        }
                    },
                    "emotional": {
                        "themes": ["understanding_emotions", "expression", "self_control"],
                        "focus": "helping children recognize and manage their emotions",
                        "key_elements": ["emotional_awareness", "feeling_expression", "emotional_control", "empathy_development", "social_emotional_learning"],
                        "story_variations": {
                            "emotional_situations": [
                                "feeling worried about trying something new",
                                "being disappointed when plans change",
                                "feeling proud after helping someone",
                                "managing anger when things don't go right",
                                "overcoming shyness to make new friends",
                                "dealing with jealousy in a healthy way"
                            ],
                            "learning_approach": [
                                "through gentle storytelling and examples",
                                "by recognizing emotions in others",
                                "through role-playing different scenarios",
                                "by talking about feelings openly",
                                "through creative expression and art"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "learning_and_discovery",
                    "approach": "interactive_hands_on",
                    "outcome": "clear_educational_value",
                    "enhancements": {
                        "learning_elements": True,
                        "problem_solving": True,
                        "character_growth": True,
                        "emotional_learning": True
                    }
                }
            }),
            ("adventure", "Adventure", {
                "focus": "exciting_exploration",
                "approach": "imaginative_scenarios",
                "subcategories": {
                    "fantasy": {
                        "themes": ["magic_worlds", "magical_creatures", "supernatural_powers"],
                        "focus": "stories set in magical worlds beyond everyday reality",
                        "key_elements": ["imaginative_settings", "fun_magic", "friendly_adventures", "safe_exploration", "colorful_characters"],
                        "layered_variations": {
                            "fantasy_worlds": [
                                "Enchanted forest with talking trees and friendly animals",
                                "Magical underwater kingdom with colorful sea creatures",
                                "Cloud city in the sky with floating islands",
                                "Crystal cave system with glowing gems and echoes",
                                "Flower meadow where plants have magical powers",
                                "Desert oasis with wise magical guardians",
                                "Mountain village where dragons are friendly helpers",
                                "Magic library where books come alive",
                                "Rainbow bridge connecting different magical realms",
                                "Starlight garden that only appears at night"
                            ],
                            "magical_elements": [
                                "discover talking animals who become helpful guides",
                                "find magical objects that solve problems with kindness",
                                "meet friendly magical creatures who need assistance",
                                "explore enchanted places that respond to emotions",
                                "learn simple magic spells that spread joy and help",
                                "use magical transportation to reach new adventures",
                                "work with magical guardians who teach wisdom"
                            ],
                            "adventure_activities": [
                                "solving gentle puzzles through teamwork",
                                "helping magical friends with creative solutions",
                                "exploring new places with wonder and curiosity",
                                "learning magical skills through practice and patience",
                                "building friendships across different magical species",
                                "using imagination to overcome simple challenges"
                            ]
                        }
                    },
                    "history_exploration": {
                        "themes": ["exploring_past", "ancient_civilizations", "legends"],
                        "focus": "introducing historical settings and famous figures in an engaging way",
                        "key_elements": ["simple_historical_context", "famous_figures", "fun_facts", "cultural_learning", "exciting_discoveries"],
                        "layered_variations": {
                            "historical_periods": [
                                "Prehistoric times with friendly dinosaurs",
                                "Ancient Egypt with pyramid builders",
                                "Medieval times with brave knights",
                                "Ancient Greece with wise philosophers",
                                "Viking era with brave explorers",
                                "Renaissance with amazing inventors",
                                "Ancient China with skilled artisans",
                                "Mayan civilization with astronomical wisdom",
                                "Stone Age with early human discoveries",
                                "Roman Empire with engineering marvels"
                            ],
                            "historical_focus_guides": [
                                "discover how people lived in their daily lives",
                                "explore the amazing inventions and tools they created",
                                "learn about the brave adventures and explorations they took",
                                "understand the beautiful art and stories they made",
                                "find out about the wise leaders and heroes of that time",
                                "explore the special buildings and monuments they built",
                                "learn about the animals and nature of that era",
                                "discover the games and celebrations they enjoyed"
                            ],
                            "learning_activities": [
                                "through imaginative time-travel adventures",
                                "by building models and replicas together",
                                "through storytelling with costumes and props",
                                "by creating art projects in historical styles",
                                "through simple experiments and demonstrations",
                                "by role-playing historical scenarios",
                                "through songs and stories from that era",
                                "by examining pictures and artifacts together"
                            ]
                        }
                    },
                    "dream_world": {
                        "themes": ["imagination", "dream_adventure", "fantastic_journey"],
                        "focus": "adventures that happen during sleep with dream-like logic",
                        "key_elements": ["dream_sequences", "magical_scenarios", "imaginative_play", "fantasy_logic", "friendly_dream_characters"],
                        "story_variations": {
                            "dream_settings": [
                                "a magical cloud city where everything floats",
                                "an underwater world with friendly sea creatures",
                                "a forest where trees can talk and sing",
                                "a candy land with gingerbread houses",
                                "a place where toys come alive at night",
                                "a rainbow bridge connecting different worlds",
                                "a library where book characters step out",
                                "a garden where flowers grant wishes"
                            ],
                            "dream_adventures": [
                                "helping lost dream creatures find their way home",
                                "solving gentle puzzles to unlock dream doors",
                                "collecting magical dream gems with special powers",
                                "teaching new friends how to fly in dreams",
                                "building dream castles with imagination blocks",
                                "going on treasure hunts for happy memories"
                            ]
                        }
                    },
                    "sci_fi": {
                        "themes": ["space", "robots", "future_tech"],
                        "focus": "imagining the future and space exploration",
                        "key_elements": ["friendly_robots", "space_travel", "future_cities", "cool_gadgets", "scientific_curiosity"],
                        "layered_variations": {
                            "sci_fi_settings": [
                                "Moon base with low gravity fun",
                                "Mars colony with red sand castles",
                                "Space station with viewing domes",
                                "Robot city where everything is automated",
                                "Future school with holographic lessons",
                                "Starship bridge with friendly AI",
                                "Alien garden with singing plants",
                                "Asteroid belt playground"
                            ],
                            "tech_elements": [
                                "universal translator for talking to aliens",
                                "gravity boots for jumping high",
                                "food replicator making favorite snacks",
                                "teleporter for instant travel",
                                "cleaning robots that like to play",
                                "learning helmets that teach instantly"
                            ],
                            "adventures": [
                                "fixing a friendly robot's loose screw",
                                "finding a lost satellite puppy",
                                "mapping a new constellation",
                                "racing solar sail boats",
                                "planting the first flower on a new planet"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "exciting_exploration",
                    "approach": "imaginative_scenarios",
                    "outcome": "thrilling_resolutions",
                    "enhancements": {
                        "exploration_elements": True,
                        "safe_challenges": True,
                        "teamwork": True,
                        "discovery": True
                    }
                }
            }),

            ("fun", "Fun", {
                "focus": "humor_entertainment",
                "approach": "playful_situations",
                "subcategories": {
                    "humor": {
                        "themes": ["funny_adventures", "playful_situations", "silly_characters"],
                        "focus": "light-hearted stories meant to make children laugh",
                        "key_elements": ["silly_moments", "unexpected_fun", "lighthearted_tone", "joyful_characters", "playful_language"],
                        "story_variations": {
                            "funny_situations": [
                                "silly mix-ups and funny misunderstandings",
                                "playful animals doing unexpected things",
                                "funny cooking experiments with surprising results",
                                "silly games that lead to hilarious adventures",
                                "funny dress-up and pretend play scenarios",
                                "amusing attempts at learning new skills"
                            ],
                            "humor_style": [
                                "through gentle slapstick and physical comedy",
                                "via funny wordplay and silly sounds",
                                "through amusing character interactions",
                                "by creating funny songs and rhymes",
                                "through playful problem-solving attempts"
                            ]
                        }
                    },
                    "puzzle_adventure": {
                        "themes": ["finding_clues", "simple_puzzles", "treasure_hunt"],
                        "focus": "engaging children in problem-solving and mysteries",
                        "key_elements": ["clue_search", "puzzle_solving", "teamwork", "logical_thinking", "exciting_discovery"],
                        "story_variations": {
                            "mystery_themes": [
                                "finding a missing pet in the neighborhood",
                                "solving the case of disappearing cookies",
                                "discovering who left mysterious gifts",
                                "figuring out why the garden flowers changed colors",
                                "finding the source of beautiful music in the house",
                                "solving the puzzle of a magical map"
                            ],
                            "puzzle_types": [
                                "picture clues that tell a story",
                                "simple riddles with fun answers",
                                "matching games with hidden meanings",
                                "counting and pattern puzzles",
                                "memory games with family photos",
                                "treasure maps with easy-to-follow directions"
                            ]
                        }
                    },
                    "creative_arts": {
                        "themes": ["painting", "music", "performance"],
                        "focus": "expressing creativity through arts",
                        "key_elements": ["artistic_expression", "musical_joy", "performance_fun", "creative_mess", "imagination"],
                        "story_variations": {
                            "art_projects": [
                                "painting a giant mural together",
                                "making instruments from recycled items",
                                "putting on a backyard play",
                                "creating a comic book story",
                                "sculpting with clay and dough",
                                "organizing a family talent show"
                            ],
                            "creative_challenges": [
                                "painting without brushes (finger painting)",
                                "making music with water glasses",
                                "acting out a story without words",
                                "drawing invisible pictures with lemon juice",
                                "building a cardboard castle"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "humor_entertainment",
                    "approach": "playful_situations",
                    "outcome": "joyful_experiences",
                    "enhancements": {
                        "humor_elements": True,
                        "playful_characters": True,
                        "amusing_scenarios": True,
                        "lighthearted_tone": True
                    }
                }
            }),
            ("cultural", "Cultural", {
                "focus": "cultural_learning",
                "approach": "respectful_exploration",
                "subcategories": {
                    "world_cultures": {
                        "themes": ["traditions", "customs", "folk_stories"],
                        "focus": "introducing cultural facts, traditions, and customs from different countries",
                        "key_elements": ["cultural_stories", "folk_tales", "positive_traditions", "cultural_learning", "fun_exploration"],
                        "layered_variations": {
                            "cultural_base": [
                                "Japan", "China", "India", "Mexico", "France",
                                "Italy", "Germany", "Korea", "Brazil", "Egypt",
                                "Thailand", "Morocco", "Peru", "Greece", "Scotland",
                                "Australia", "Nigeria", "Argentina", "Turkey", "Vietnam"
                            ],
                            "cultural_aspect_guides": [
                                "explore a joyful traditional festival or celebration from this culture",
                                "discover a beautiful ancient craft or artistic tradition suitable for families",
                                "learn about a heartwarming family tradition passed through generations",
                                "experience traditional music, dance, or storytelling methods that children enjoy",
                                "explore traditional foods and their cultural significance in family settings",
                                "understand traditional clothing and what it represents in positive ways",
                                "discover traditional children's games and activities that are educational and fun",
                                "learn about traditional wisdom, folktales, or legends appropriate for young minds"
                            ],
                            "interaction_multipliers": [
                                "through hands-on activities they can try at home",
                                "by creating something together using traditional methods",
                                "through storytelling with props and role-playing",
                                "by cooking or preparing traditional foods safely",
                                "through music, songs, or simple dances",
                                "by building or decorating cultural items",
                                "through games and interactive learning",
                                "by connecting with nature in traditional ways"
                            ]
                        }
                    },
                    "diversity": {
                        "themes": ["acceptance", "respect", "inclusion"],
                        "focus": "promoting kindness and respect for people from different backgrounds",
                        "key_elements": ["positive_interactions", "friendly_characters", "cooperation", "kind_behavior", "social_inclusion"],
                        "story_variations": {
                            "diversity_scenarios": [
                                "meeting a new friend who speaks a different language",
                                "learning about different family traditions",
                                "discovering that everyone has unique talents",
                                "helping someone who looks different feel welcome",
                                "sharing games and activities from different cultures",
                                "learning that differences make friendships more interesting"
                            ],
                            "inclusion_activities": [
                                "playing games that everyone can enjoy together",
                                "sharing favorite foods from different families",
                                "learning simple words in different languages",
                                "creating art projects that celebrate differences",
                                "telling stories about family backgrounds",
                                "working together on community helper projects"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "cultural_learning",
                    "approach": "respectful_exploration",
                    "outcome": "understanding_diversity",
                    "enhancements": {
                        "cultural_elements": True,
                        "traditions": True,
                        "diversity_celebration": True,
                        "respectful_learning": True
                    }
                }
            }),
            ("environmental", "Environmental", {
                "focus": "nature_appreciation",
                "approach": "hands_on_activities",
                "subcategories": {
                    "nature_care": {
                        "themes": ["protecting_nature", "recycling", "helping_animals"],
                        "focus": "raising awareness about protecting nature and animals in simple ways",
                        "key_elements": ["green_habits", "caring_for_animals", "eco_friendly_behaviors", "positive_environmental_actions", "nature_exploration"],
                        "layered_variations": {
                            "environmental_settings": [
                                "Home garden and backyard ecosystem",
                                "Local park and community green spaces",
                                "Forest and woodland environments",
                                "Beach and ocean conservation areas",
                                "River and freshwater habitats",
                                "Urban environment and city nature",
                                "School grounds and educational gardens",
                                "Farm and agricultural landscapes"
                            ],
                            "conservation_actions": [
                                "learn how to protect and help local wildlife",
                                "discover ways to reduce waste and reuse materials creatively",
                                "explore how to save energy and water in daily life",
                                "understand how plants and animals depend on each other",
                                "find out how clean air and water benefit everyone",
                                "learn about renewable energy through simple examples",
                                "discover how small actions create big environmental changes"
                            ],
                            "action_methods": [
                                "hands-on projects they can do at home",
                                "outdoor exploration and nature observation",
                                "creative recycling and upcycling activities",
                                "simple gardening and plant care",
                                "wildlife watching and habitat building",
                                "community involvement and family projects",
                                "experiments that demonstrate environmental concepts",
                                "artistic projects using natural materials"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "nature_appreciation",
                    "approach": "hands_on_activities",
                    "outcome": "environmental_awareness",
                    "enhancements": {
                        "nature_elements": True,
                        "environmental_care": True,
                        "hands_on_learning": True,
                        "positive_action": True
                    }
                }
            }),
            ("classic", "Classic", {
                "focus": "timeless_storytelling",
                "approach": "gentle_retellings",
                "subcategories": {
                    "gentle_fairy_tales": {
                        "themes": ["classic_adaptations", "friendly_fairy_stories", "moral_tales"],
                        "focus": "traditional fairy tales adapted in gentle, kid-friendly versions",
                        "key_elements": ["timeless_plots", "magical_elements", "gentle_characters", "positive_endings", "traditional_storytelling"],
                        "story_variations": {
                            "fairy_tale_adaptations": [
                                "a gentle version of Goldilocks learning about respect",
                                "three little pigs who solve problems through friendship",
                                "a kind-hearted giant who helps his community",
                                "a princess who saves the day with her cleverness",
                                "a brave little tailor who uses wit instead of force",
                                "a magical shoemaker who teaches about helping others"
                            ],
                            "magical_elements": [
                                "talking animals who give wise advice",
                                "magical objects that reward kindness",
                                "fairy godparents who teach important lessons",
                                "enchanted forests where friendship conquers all",
                                "magical transformations that show inner beauty",
                                "wishing wells that grant selfless wishes"
                            ]
                        }
                    }
                },
                "adaptation_rules": {
                    "focus": "timeless_storytelling",
                    "approach": "gentle_retellings",
                    "outcome": "classic_values",
                    "enhancements": {
                        "traditional_elements": True,
                        "modern_adaptations": True,
                        "classic_values": True,
                        "contemporary_relevance": True
                    }
                }
            }),
        ]
        
        for node_id, label, props in categories:
            self.add_node(node_id, NodeType.CATEGORY, label, props)

        # 子類別節點：將 category.properties["subcategories"] 節點化，讓其可被關係查詢
        for category_id, _, category_props in categories:
            subcategories = (category_props or {}).get("subcategories", {})
            if not isinstance(subcategories, dict):
                continue
            for subcat_id, subcat_props in subcategories.items():
                subcat_node_id = f"subcat_{category_id}_{subcat_id}"
                self.add_node(
                    subcat_node_id,
                    NodeType.SUBCATEGORY,
                    _format_label(subcat_id),
                    {
                        "category_id": category_id,
                        "subcategory_id": subcat_id,
                        "config": subcat_props,
                    },
                )
                self.add_edge(category_id, subcat_node_id, "has_subcategory")

                # 如果 subcategory themes 指向已存在的 Theme node，建立 supports_theme
                themes = (subcat_props or {}).get("themes")
                if isinstance(themes, list):
                    for theme_key in themes:
                        if isinstance(theme_key, str) and theme_key in self.nodes:
                            if self.nodes[theme_key].type == NodeType.THEME:
                                self.add_edge(subcat_node_id, theme_key, "supports_theme")
                        elif isinstance(theme_key, str):
                            # 不存在的 theme key 視為概念 (concept)
                            concept_id = f"concept_{theme_key.strip().lower().replace(' ', '_')}"
                            if concept_id not in self.nodes:
                                self.add_node(
                                    concept_id,
                                    NodeType.CONCEPT,
                                    _format_label(theme_key),
                                    {"source": "subcategory_theme_list"},
                                )
                            self.add_edge(subcat_node_id, concept_id, "covers_concept")
        
        # 主題節點 - 擴展配置
        self.themes = [
            ("sharing", "Sharing", {
                "category": "educational", 
                "moral_value": "cooperation",
                "situations": [
                    "deciding whether to share their favorite snack",
                    "helping a friend who is feeling sad",
                    "including a new child in their games"
                ]
            }),
            ("friendship", "Friendship", {
                "category": "educational", 
                "moral_value": "social",
                "friendship_activities": [
                    "playing games that everyone can enjoy together",
                    "working together on community helper projects",
                    "sharing favorite foods from different families"
                ]
            }),
            ("honesty", "Honesty", {
                "category": "educational",
                "moral_value": "integrity",
                "honesty_scenarios": [
                    "telling the truth about breaking something",
                    "admitting mistakes and making things right",
                    "choosing honesty even when it's hard"
                ]
            }),
            ("emotional_growth", "Emotional Growth", {
                "category": "educational",
                "emotional_focus": "self_regulation",
                "learning_approach": [
                    "talking about feelings openly",
                    "role-playing different emotional scenarios",
                    "using art or music to express feelings"
                ]
            }),
            ("animals_exploration", "Animal Discovery", {
                "category": "educational",
                "knowledge_domain": "animals",
                "discovery_paths": [
                    "observing how animals move and communicate",
                    "learning how animals build homes",
                    "comparing animal families and routines"
                ]
            }),
            ("courage", "Courage", {
                "category": "adventure", 
                "emotional_value": "confidence",
                "courage_scenarios": [
                    "trying something new with friends' support",
                    "standing up for what's right in a gentle way",
                    "helping someone who needs assistance"
                ]
            }),
            ("magic", "Magic", {
                "category": "adventure", 
                "imagination": "high",
                "magic_elements": [
                    "talking animals who give wise advice",
                    "magical objects that reward kindness",
                    "enchanted places where friendship matters most"
                ]
            }),
            ("dream_adventure", "Dream Adventure", {
                "category": "adventure",
                "imagination": "surreal",
                "dream_prompts": [
                    "floating through a rainbow sky",
                    "meeting friendly dream guides",
                    "repairing star bridges at night"
                ]
            }),
            ("humor", "Humor", {
                "category": "fun", 
                "entertainment": "high",
                "humor_types": [
                    "gentle slapstick and physical comedy",
                    "funny wordplay and silly sounds",
                    "amusing character interactions"
                ]
            }),
            ("puzzle_solving", "Puzzle Solving", {
                "category": "fun",
                "engagement": "interactive",
                "puzzle_styles": [
                    "matching clues to pictures",
                    "following simple treasure maps",
                    "assembling story puzzles with friends"
                ]
            }),
            ("traditions", "Traditions", {
                "category": "cultural",
                "cultural_focus": "world_cultures",
                "elements": [
                    "celebrating joyful traditional festivals",
                    "learning respectful greetings from many countries",
                    "sharing family customs that honor elders"
                ]
            }),
            ("inclusion", "Inclusion", {
                "category": "cultural",
                "cultural_focus": "diversity",
                "elements": [
                    "welcoming classmates from new places",
                    "listening to stories told in different languages",
                    "discovering talents that make each friend unique"
                ]
            }),
            ("nature_care_theme", "Nature Care", {
                "category": "environmental",
                "environmental_focus": "care_actions",
                "activities": [
                    "planting seeds and watching them grow",
                    "creating recycling stations at home",
                    "building tiny habitats for local animals"
                ]
            }),
            ("recycling_fun", "Recycling Fun", {
                "category": "environmental",
                "environmental_focus": "recycle_projects",
                "activities": [
                    "turning jars into friendly lanterns",
                    "making musical instruments from boxes",
                    "designing art from bottle caps"
                ]
            }),
            ("classic_values", "Classic Values", {
                "category": "classic",
                "story_focus": "gentle_lessons",
                "motifs": [
                    "kindness is rewarded with magic",
                    "clever thinking solves problems",
                    "friendship transforms classic endings"
                ]
            }),
        ]
        
        for node_id, label, props in self.themes:
            self.add_node(node_id, NodeType.THEME, label, props)

        # 主題概念化：將可控的 scalar 屬性轉成 Concept 節點，讓 subcategory/theme 可以用概念做連結與推論。
        # 這會提高「一致性」與「可解釋性」，也能讓生成端的選擇不是純隨機。
        for theme_id, _, theme_props in self.themes:
            if isinstance(theme_props, dict):
                self._add_theme_concepts(theme_id, theme_props)

        # 場景節點：將主題內的 list props（situations/activities/...）節點化為 SCENE
        # 並用 THEME -> SCENE (suggests_scene) 連結，供生成模組取得更穩定的 scenes。
        for theme_id, _, theme_props in self.themes:
            if not isinstance(theme_props, dict):
                continue
            for value in theme_props.values():
                if not isinstance(value, list):
                    continue
                for item in value:
                    if not isinstance(item, str):
                        continue
                    scene_key = item.strip().lower()
                    if not scene_key:
                        continue
                    scene_id = "scene_" + re.sub(r"[^a-z0-9]+", "_", scene_key).strip("_")[:80]
                    if scene_id not in self.nodes:
                        # Classify scene type intelligently
                        scene_type = self._classify_scene_type(item.strip())
                        self.add_node(
                            scene_id,
                            NodeType.SCENE,
                            item.strip(),
                            {
                                "source": "theme_list_prop",
                                "scene_type": scene_type,
                                "complexity": self._estimate_scene_complexity(item.strip()),
                            },
                        )
                    self.add_edge(theme_id, scene_id, "suggests_scene")
        
        # 角色節點
        characters = [
            ("grandpa_tom", "Grandpa Tom", {
                "age": "elderly", "role": "guide", 
                "personality": "wise", "appearance": "silver hair, green cardigan",
                "emotional_range": ["patience", "warmth", "pride", "gentle_concern"],
                "teaching_style": "storytelling_and_demonstration"
            }),
            ("emma", "Emma", {
                "age": "child", "role": "protagonist",
                "personality": "curious", "appearance": "golden hair, red dress",
                "emotional_range": ["curiosity", "joy", "determination", "empathy"],
                "learning_style": "hands_on_exploration"
            }),
            ("alex", "Alex", {
                "age": "toddler", "role": "companion",
                "personality": "innocent", "appearance": "brown hair, blue overalls",
                "emotional_range": ["wonder", "surprise", "delight", "gentle_worry"],
                "learning_style": "observation_and_imitation"
            })
        ]
        
        for node_id, label, props in characters:
            self.add_node(node_id, NodeType.CHARACTER, label, props)
        
        # 角色關係網絡
        character_relationships = [
            ("grandpa_tom", "emma", "grandparent_of"),
            ("grandpa_tom", "alex", "grandparent_of"),
            ("emma", "alex", "sibling_of"),
            ("emma", "grandpa_tom", "grandchild_of"),
            ("alex", "grandpa_tom", "grandchild_of"),
            ("alex", "emma", "sibling_of"),
        ]
        
        for source, target, rel_type in character_relationships:
            self.add_edge(source, target, "related_to", {"relationship_type": rel_type})
        
        # 添加通用故事變化元素（需先定義，因為 _add_initial_relations 會用到）
        self._add_story_variations()
        
        # 添加關係
        self._add_initial_relations()

    def _concept_id_from_value(self, value: str) -> str:
        slug = value.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
        slug = slug[:80] if slug else "general"
        return f"concept_{slug}"

    def _add_theme_concepts(self, theme_id: str, theme_props: Dict[str, Any]) -> None:
        """將主題的一部分屬性概念化。

        原則：只概念化「可作為知識抽象」的 scalar 欄位，避免把 scenes/prompts 也當概念導致噪音。
        """
        if theme_id not in self.nodes:
            return
        if not isinstance(theme_props, dict):
            return

        scalar_keys = {
            "knowledge_domain",
            "moral_value",
            "emotional_value",
            "environmental_focus",
            "cultural_focus",
            "entertainment",
            "engagement",
            "imagination",
            "story_focus",
            "focus",
        }

        for key, value in theme_props.items():
            if key not in scalar_keys:
                continue
            if not isinstance(value, str) or not value.strip():
                continue
            concept_id = self._concept_id_from_value(value)
            if concept_id not in self.nodes:
                self.add_node(
                    concept_id,
                    NodeType.CONCEPT,
                    _format_label(value),
                    {
                        "source": "theme_scalar_prop",
                        "value": value,
                    },
                )
            # Edge 屬性紀錄 concept 的「來源欄位」= kind，供下游解釋與過濾。
            self.add_edge(theme_id, concept_id, "involves_concept", {"kind": key})

    def get_theme_scenes(self, theme_id: str) -> List[str]:
        """取得某個主題可用的場景描述（從圖譜關係 suggests_scene 取得）。"""
        if theme_id not in self.nodes:
            return []
        targets = self.get_targets_by_relation(theme_id, "suggests_scene")
        return [node.label for node in targets if node and node.type == NodeType.SCENE]
    
    def _classify_scene_type(self, scene_text: str) -> str:
        """智能分類場景類型。"""
        text_lower = scene_text.lower()
        
        # 定義關鍵詞模式
        patterns = {
            "outdoor": ["outside", "garden", "park", "forest", "nature", "tree", "field", "beach", "mountain", "walk"],
            "indoor": ["home", "house", "room", "kitchen", "inside", "table", "bed"],
            "magical": ["magic", "magical", "enchanted", "fairy", "mystical", "sparkle", "glow", "dream"],
            "educational": ["learn", "teach", "discover", "explore", "study", "book", "lesson"],
            "emotional": ["feel", "happy", "sad", "worried", "excited", "proud", "love", "care"],
            "interactive": ["play", "game", "together", "help", "build", "make", "create"],
            "adventure": ["adventure", "journey", "quest", "find", "search", "mystery"],
        }
        
        # 計算每種類型的匹配分數
        scores = {scene_type: 0 for scene_type in patterns}
        for scene_type, keywords in patterns.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[scene_type] += 1
        
        # 返回最高分的類型
        max_score = max(scores.values())
        if max_score > 0:
            return max((k for k, v in scores.items() if v == max_score), key=lambda x: scores[x])
        return "general"
    
    def _estimate_scene_complexity(self, scene_text: str) -> str:
        """估計場景複雜度。"""
        word_count = len(scene_text.split())
        if word_count <= 5:
            return "simple"
        elif word_count <= 10:
            return "moderate"
        else:
            return "complex"
    
    
    def get_random_branch_archetypes(self, count: int, age_group: str, rng: Optional[random.Random] = None) -> List[Dict[str, str]]:
        """
        Randomly selects a diverse set of branch archetypes suitable for the age group.
        Ensures strict uniqueness (no duplicates).
        """
        roller = self._get_rng(rng)
        
        # Filter suitable archetypes
        candidates = []
        for key, data in BRANCH_ARCHETYPES.items():
            if "all" in data["suitable_ages"] or age_group in data["suitable_ages"]:
                candidates.append({"type": key, **data})
                
        # Shuffle and select
        roller.shuffle(candidates)
        
        if len(candidates) < count:
            # Should not happen given we have 10+ types, but fallback safely
            # Fill remainder with generic type if needed, or just cycle
            padding = candidates * (count // len(candidates) + 1)
            candidates = padding
            
        return candidates[:count]

    def _add_story_variations(self):
        """添加通用故事變化元素"""
        
        # 故事結構變化
        story_structures = [
            ("mystery_solving_together", "Mystery Solving Together", "a mystery that needs solving together"),
            ("creative_project_step_by_step", "Creative Project", "a creative project they build step by step"),
            ("problem_solving_adventure", "Problem Solving Adventure", "a problem-solving adventure"),
            ("interactive_teaching_moment", "Interactive Teaching", "a teaching moment that becomes interactive"),
            ("discovery_journey_surprises", "Discovery Journey", "a discovery journey with surprises"),
            ("collaborative_game", "Collaborative Game", "a collaborative game or challenge"),
            ("storytelling_comes_alive", "Storytelling Comes Alive", "a storytelling session that comes alive"),
            ("lost_and_found_quest", "Lost and Found", "a quest to find something lost and return it"),
            ("helping_a_new_friend", "New Friend Help", "helping a new friend overcome a challenge"),
            ("preparing_for_celebration", "Celebration Prep", "preparing for a special celebration or event"),
            ("nature_rescue_mission", "Nature Rescue", "a mission to help a plant or animal in need"),
            ("overcoming_fear_together", "Overcoming Fear", "facing a small fear together with support")
        ]
        
        for key, label, desc in story_structures:
            self.add_node(
                f"structure_{key}",
                NodeType.GENERATION_PARAM,
                label,
                {
                    "type": "story_structure",
                    "variation_type": key,
                    "description": desc
                }
            )
        
        # 角色動態變化
        character_dynamics = [
            ("emma_curious", "Emma's Curiosity", "Emma shows natural curiosity and asks lots of questions"),
            ("alex_innocent", "Alex's Observations", "Alex contributes with innocent and surprising observations"),
            ("grandpa_wise", "Grandpa's Wisdom", "Grandpa Tom patiently guides and shares his wisdom"),
            ("happy_learning_team", "Learning Team", "all three work together as a happy learning team"),
            ("kids_help_each_other", "Peer Learning", "Emma and Alex help each other understand new things"),
            ("grandpa_storyteller", "Grandpa's Stories", "Grandpa Tom tells engaging stories from his experiences"),
            ("children_inspire_grandpa", "Fresh Perspectives", "the children inspire Grandpa Tom with their fresh perspectives"),
            ("emma_leads_adventure", "Emma Leads", "Emma takes the lead in the adventure with confidence"),
            ("alex_finds_clue", "Alex Finds Clue", "Alex notices a small detail that solves the problem"),
            ("grandpa_learns_new_tech", "Grandpa Learns", "Grandpa Tom learns something new from the children"),
            ("team_problem_solving", "Team Solving", "each character contributes a different skill to solve the problem")
        ]
        
        for key, label, desc in character_dynamics:
            self.add_node(
                f"dynamic_{key}",
                NodeType.GENERATION_PARAM,
                label,
                {
                    "type": "character_dynamic",
                    "variation_type": key,
                    "description": desc
                }
            )
        
        # 故事催化劑
        story_catalysts = [
            ("mysterious_object_house", "Mysterious Object", "a mysterious object found in the house"),
            ("neighbor_question", "Neighbor's Question", "a question from a neighbor child"),
            ("interesting_walk", "Interesting Walk", "something interesting seen on a walk"),
            ("imagination_book", "Inspiring Book", "a book that sparks imagination"),
            ("family_photo_story", "Family Photo", "a family photo that tells a story"),
            ("cooking_experiment", "Cooking Experiment", "a cooking experiment gone interesting"),
            ("unexpected_visitor", "Unexpected Visitor", "an unexpected visitor or delivery"),
            ("seasonal_change_learning", "Seasonal Change", "a seasonal change that inspires learning"),
            ("strange_sound_attic", "Strange Sound", "a strange but friendly sound coming from the attic or garden"),
            ("old_map_discovery", "Old Map", "an old map found inside a library book"),
            ("broken_toy_repair", "Broken Toy", "a favorite toy breaks and needs creative fixing"),
            ("weather_surprise", "Weather Surprise", "a sudden weather change brings a new adventure"),
            ("animal_track_mystery", "Animal Tracks", "strange animal tracks found in the mud")
        ]
        
        for key, label, desc in story_catalysts:
            self.add_node(
                f"catalyst_{key}",
                NodeType.GENERATION_PARAM,
                label,
                {
                    "type": "story_catalyst",
                    "variation_type": key,
                    "description": desc
                }
            )
            
        # =============================================================================
        # 建立變數與類別/年齡層的語義連結 (Semantic Linking)
        # 這將孤立的變數節點整合進知識圖譜網絡中，使其成為真正的 KG
        # =============================================================================
        
        # 1. 結構 -> 類別 (Structure -> Category)
        structure_category_map = [
            ("mystery_solving_together", ["adventure", "fun"]),
            ("creative_project_step_by_step", ["educational", "fun", "cultural"]),
            ("problem_solving_adventure", ["adventure", "educational"]),
            ("interactive_teaching_moment", ["educational", "cultural"]),
            ("discovery_journey_surprises", ["adventure", "environmental"]),
            ("collaborative_game", ["fun", "educational"]),
            ("storytelling_comes_alive", ["cultural", "classic"]),
            ("lost_and_found_quest", ["adventure", "fun"]),
            ("helping_a_new_friend", ["educational", "cultural"]),
            ("preparing_for_celebration", ["cultural", "fun"]),
            ("nature_rescue_mission", ["environmental", "adventure"]),
            ("overcoming_fear_together", ["educational", "adventure"])
        ]
        
        for struct_key, categories in structure_category_map:
            for cat in categories:
                self.add_edge(f"structure_{struct_key}", cat, "structure_suitable_for")

        # 2. 催化劑 -> 類別 (Catalyst -> Category)
        catalyst_category_map = [
            ("mysterious_object_house", ["adventure", "fun"]),
            ("neighbor_question", ["educational", "cultural"]),
            ("interesting_walk", ["environmental", "adventure"]),
            ("imagination_book", ["adventure", "classic"]),
            ("family_photo_story", ["cultural", "classic"]),
            ("cooking_experiment", ["fun", "educational"]),
            ("unexpected_visitor", ["adventure", "fun"]),
            ("seasonal_change_learning", ["environmental", "educational"]),
            ("strange_sound_attic", ["adventure", "fun"]),
            ("old_map_discovery", ["adventure", "cultural"]),
            ("broken_toy_repair", ["educational", "fun"]),
            ("weather_surprise", ["environmental", "adventure"]),
            ("animal_track_mystery", ["environmental", "adventure"])
        ]
        
        for cat_key, categories in catalyst_category_map:
            for cat in categories:
                self.add_edge(f"catalyst_{cat_key}", cat, "catalyst_fits_category")

        # 3. 動態 -> 年齡層 (Dynamic -> Age Group)
        # 某些互動模式需要較高的認知能力
        dynamic_age_map = [
            ("emma_curious", ["age_2_3", "age_4_5", "age_6_8", "age_9_10"]),
            ("alex_innocent", ["age_2_3", "age_4_5", "age_6_8"]),
            ("grandpa_wise", ["age_2_3", "age_4_5", "age_6_8", "age_9_10"]),
            ("happy_learning_team", ["age_4_5", "age_6_8", "age_9_10"]),
            ("kids_help_each_other", ["age_6_8", "age_9_10"]),
            ("grandpa_storyteller", ["age_2_3", "age_4_5", "age_6_8"]),
            ("children_inspire_grandpa", ["age_6_8", "age_9_10"]),
            ("emma_leads_adventure", ["age_6_8", "age_9_10"]),
            ("alex_finds_clue", ["age_4_5", "age_6_8"]),
            ("grandpa_learns_new_tech", ["age_6_8", "age_9_10"]),
            ("team_problem_solving", ["age_6_8", "age_9_10"])
        ]
        
        for dyn_key, ages in dynamic_age_map:
            for age in ages:
                self.add_edge(f"dynamic_{dyn_key}", age, "dynamic_suitable_for_age")
        
        # =============================================================================
        # 情感節點 (Emotion Nodes)
        # =============================================================================
        emotions = [
            ("joy", "Joy", {"description": "happiness and delight", "age_range": "all", "intensity": "positive_high"}),
            ("curiosity", "Curiosity", {"description": "wonder and desire to learn", "age_range": "all", "intensity": "positive_medium"}),
            ("empathy", "Empathy", {"description": "understanding others' feelings", "age_range": "4+", "intensity": "positive_medium"}),
            ("pride", "Pride", {"description": "satisfaction in achievement", "age_range": "all", "intensity": "positive_medium"}),
            ("disappointment", "Disappointment", {"description": "gentle sadness when plans change", "age_range": "4+", "intensity": "negative_low"}),
            ("fear_mild", "Mild Fear", {"description": "manageable worry or concern", "age_range": "6+", "intensity": "negative_low"}),
            ("surprise", "Surprise", {"description": "unexpected delight", "age_range": "all", "intensity": "neutral_high"}),
            ("determination", "Determination", {"description": "resolve to accomplish something", "age_range": "6+", "intensity": "positive_medium"}),
            ("gratitude", "Gratitude", {"description": "thankfulness and appreciation", "age_range": "4+", "intensity": "positive_medium"}),
            ("patience", "Patience", {"description": "calm waiting and understanding", "age_range": "6+", "intensity": "positive_low"}),
        ]
        
        for emotion_id, label, props in emotions:
            self.add_node(f"emotion_{emotion_id}", NodeType.EMOTION, label, props)
        
        # =============================================================================
        # 學習目標節點 (Learning Objective Nodes)
        # =============================================================================
        self.learning_objectives = [
            ("counting_1_10", "Counting 1-10", {"domain": "math", "age_start": 2, "age_end": 5}),
            ("color_recognition", "Color Recognition", {"domain": "cognitive", "age_start": 2, "age_end": 4}),
            ("cause_effect", "Cause and Effect", {"domain": "science", "age_start": 4, "age_end": 8}),
            ("empathy_development", "Empathy Development", {"domain": "social_emotional", "age_start": 4, "age_end": 10}),
            ("sharing_cooperation", "Sharing and Cooperation", {"domain": "social_emotional", "age_start": 2, "age_end": 6}),
            ("problem_solving", "Problem Solving", {"domain": "cognitive", "age_start": 4, "age_end": 10}),
            ("pattern_recognition", "Pattern Recognition", {"domain": "math", "age_start": 3, "age_end": 7}),
            ("emotional_regulation", "Emotional Regulation", {"domain": "social_emotional", "age_start": 4, "age_end": 10}),
            ("basic_science_concepts", "Basic Science Concepts", {"domain": "science", "age_start": 5, "age_end": 10}),
            ("storytelling_skills", "Storytelling Skills", {"domain": "language", "age_start": 4, "age_end": 10}),
        ]
        
        for obj_id, label, props in self.learning_objectives:
            self.add_node(f"learning_{obj_id}", NodeType.LEARNING_OBJECTIVE, label, props)
        
        # =============================================================================
        # 故事節奏元素 (Pacing Element Nodes)
        # =============================================================================
        self.pacing_elements = [
            ("gentle_intro", "Gentle Introduction", {"phase": "opening", "tension": "low", "description": "calm and inviting start"}),
            ("curiosity_buildup", "Curiosity Buildup", {"phase": "rising", "tension": "medium", "description": "gradually increasing interest"}),
            ("surprise_moment", "Surprise Moment", {"phase": "middle", "tension": "medium_high", "description": "unexpected but delightful twist"}),
            ("challenge_point", "Challenge Point", {"phase": "climax", "tension": "high", "description": "main problem or obstacle"}),
            ("resolution_joy", "Joyful Resolution", {"phase": "falling", "tension": "medium", "description": "problem solved with happiness"}),
            ("peaceful_ending", "Peaceful Ending", {"phase": "closing", "tension": "low", "description": "calm and satisfying conclusion"}),
            ("reflection_moment", "Reflection Moment", {"phase": "closing", "tension": "low", "description": "time to think about what was learned"}),
        ]
        
        for pacing_id, label, props in self.pacing_elements:
            self.add_node(f"pacing_{pacing_id}", NodeType.PACING_ELEMENT, label, props)
        
        # =============================================================================
        # 角色成長弧線 (Character Arc Nodes)
        # =============================================================================
        character_arcs = [
            ("overcoming_shyness", "Overcoming Shyness", {"development_type": "confidence", "suitable_ages": [4, 5, 6, 7, 8]}),
            ("learning_to_share", "Learning to Share", {"development_type": "social_skills", "suitable_ages": [2, 3, 4, 5, 6]}),
            ("gaining_confidence", "Gaining Confidence", {"development_type": "self_esteem", "suitable_ages": [5, 6, 7, 8, 9, 10]}),
            ("accepting_change", "Accepting Change", {"development_type": "adaptability", "suitable_ages": [5, 6, 7, 8, 9, 10]}),
            ("developing_patience", "Developing Patience", {"development_type": "self_control", "suitable_ages": [4, 5, 6, 7, 8]}),
            ("discovering_talent", "Discovering a Talent", {"development_type": "self_discovery", "suitable_ages": [6, 7, 8, 9, 10]}),
            ("making_first_friend", "Making First Friend", {"development_type": "social_skills", "suitable_ages": [3, 4, 5, 6]}),
            ("standing_up_for_right", "Standing Up for What's Right", {"development_type": "moral_courage", "suitable_ages": [6, 7, 8, 9, 10]}),
        ]
        
        for arc_id, label, props in character_arcs:
            self.add_node(f"arc_{arc_id}", NodeType.CHARACTER_ARC, label, props)
        
        # =============================================================================
        # 文化元素 (Cultural Element Nodes)
        # =============================================================================
        cultural_elements = [
            ("chinese_new_year", "Chinese New Year", {"region": "East Asia", "type": "festival", "key_concepts": ["family reunion", "red envelopes", "dragon dance"]}),
            ("diwali", "Diwali", {"region": "South Asia", "type": "festival", "key_concepts": ["lights", "family gathering", "sweets"]}),
            ("thanksgiving", "Thanksgiving", {"region": "North America", "type": "festival", "key_concepts": ["gratitude", "family meal", "sharing"]}),
            ("mid_autumn_festival", "Mid-Autumn Festival", {"region": "East Asia", "type": "festival", "key_concepts": ["moon", "mooncakes", "family unity"]}),
            ("storytelling_tradition", "Storytelling Tradition", {"region": "universal", "type": "custom", "key_concepts": ["oral history", "wisdom sharing", "intergenerational bond"]}),
            ("respect_for_elders", "Respect for Elders", {"region": "universal", "type": "value", "key_concepts": ["wisdom", "gratitude", "care"]}),
            ("community_helping", "Community Helping", {"region": "universal", "type": "value", "key_concepts": ["cooperation", "kindness", "shared responsibility"]}),
        ]
        
        for cultural_id, label, props in cultural_elements:
            self.add_node(f"cultural_{cultural_id}", NodeType.CULTURAL_ELEMENT, label, props)
        
        # =============================================================================
        # 視覺風格 (Visual Style Nodes)
        # =============================================================================
        visual_styles = [
            ("soft_watercolor", "Soft Watercolor", {"mood": "gentle", "age_range": "2-5", "characteristics": ["pastel colors", "soft edges", "dreamy"]}),
            ("bold_cartoon", "Bold Cartoon", {"mood": "energetic", "age_range": "4-8", "characteristics": ["bright colors", "clear outlines", "expressive"]}),
            ("storybook_realistic", "Storybook Realistic", {"mood": "warm", "age_range": "6-10", "characteristics": ["detailed", "natural lighting", "engaging"]}),
            ("whimsical_fantasy", "Whimsical Fantasy", {"mood": "magical", "age_range": "4-10", "characteristics": ["sparkles", "imaginative", "colorful"]}),
            ("nature_inspired", "Nature Inspired", {"mood": "calm", "age_range": "all", "characteristics": ["earth tones", "organic shapes", "peaceful"]}),
        ]
        
        for style_id, label, props in visual_styles:
            self.add_node(f"style_{style_id}", NodeType.VISUAL_STYLE, label, props)
    
    def _add_initial_relations(self):
        """添加初始關係"""
        
        # 年齡組適用性關係
        age_category_relations = [
            ("age_2_3", "educational", "suitable_for"),
            ("age_2_3", "fun", "suitable_for"),
            ("age_2_3", "environmental", "suitable_for"),
            ("age_2_3", "classic", "suitable_for"),
            ("age_4_5", "educational", "suitable_for"),
            ("age_4_5", "fun", "suitable_for"),
            ("age_4_5", "adventure", "suitable_for"),
            ("age_4_5", "environmental", "suitable_for"),
            ("age_4_5", "classic", "suitable_for"),
            ("age_6_8", "educational", "suitable_for"),
            ("age_6_8", "fun", "suitable_for"),
            ("age_6_8", "adventure", "suitable_for"),
            ("age_6_8", "cultural", "suitable_for"),
            ("age_6_8", "environmental", "suitable_for"),
            ("age_6_8", "classic", "suitable_for"),
            ("age_9_10", "educational", "suitable_for"),
            ("age_9_10", "fun", "suitable_for"),
            ("age_9_10", "adventure", "suitable_for"),
            ("age_9_10", "cultural", "suitable_for"),
            ("age_9_10", "environmental", "suitable_for"),
            ("age_9_10", "classic", "suitable_for"),
        ]
        
        for source, target, relation in age_category_relations:
            self.add_edge(source, target, relation)
        
        # 類別包含主題關係
        category_theme_relations = [
            ("educational", "sharing", "contains_theme"),
            ("educational", "friendship", "contains_theme"),
            ("educational", "honesty", "contains_theme"),
            ("educational", "emotional_growth", "contains_theme"),
            ("educational", "animals_exploration", "contains_theme"),
            ("adventure", "courage", "contains_theme"),
            ("adventure", "magic", "contains_theme"),
            ("adventure", "dream_adventure", "contains_theme"),
            ("fun", "humor", "contains_theme"),
            ("fun", "puzzle_solving", "contains_theme"),
            ("cultural", "traditions", "contains_theme"),
            ("cultural", "inclusion", "contains_theme"),
            ("environmental", "nature_care_theme", "contains_theme"),
            ("environmental", "recycling_fun", "contains_theme"),
            ("classic", "classic_values", "contains_theme"),
        ]
        
        for source, target, relation in category_theme_relations:
            self.add_edge(source, target, relation)
        
        # 角色出現關係
        character_category_relations = [
            ("grandpa_tom", "educational", "appears_in"),
            ("grandpa_tom", "cultural", "appears_in"),
            ("grandpa_tom", "environmental", "appears_in"),
            ("grandpa_tom", "classic", "appears_in"),
            ("emma", "educational", "appears_in"),
            ("emma", "adventure", "appears_in"),
            ("emma", "environmental", "appears_in"),
            ("emma", "classic", "appears_in"),
            ("alex", "fun", "appears_in"),
            ("alex", "educational", "appears_in"),
            ("alex", "environmental", "appears_in"),
        ]
        
        for source, target, relation in character_category_relations:
            self.add_edge(source, target, relation)
        
        # =============================================================================
        # 情感關係 (Emotion Relations)
        # =============================================================================
        
        # Theme -> Emotion (teaches_emotion)
        theme_emotion_relations = [
            ("sharing", "emotion_empathy"),
            ("sharing", "emotion_joy"),
            ("friendship", "emotion_joy"),
            ("friendship", "emotion_empathy"),
            ("honesty", "emotion_pride"),
            ("honesty", "emotion_determination"),
            ("emotional_growth", "emotion_empathy"),
            ("emotional_growth", "emotion_patience"),
            ("courage", "emotion_determination"),
            ("courage", "emotion_pride"),
            ("humor", "emotion_joy"),
            ("humor", "emotion_surprise"),
        ]
        
        for theme, emotion in theme_emotion_relations:
            self.add_edge(theme, emotion, "teaches_emotion")
        
        # Age Group -> Emotion (appropriate_emotion_for_age)
        age_emotion_relations = [
            # Age 2-3: Basic positive emotions
            ("age_2_3", "emotion_joy"),
            ("age_2_3", "emotion_curiosity"),
            ("age_2_3", "emotion_surprise"),
            ("age_2_3", "emotion_pride"),  # Added: toddlers show pride in achievements
            # Age 4-5: Expanding emotional range
            ("age_4_5", "emotion_joy"),
            ("age_4_5", "emotion_curiosity"),
            ("age_4_5", "emotion_surprise"),
            ("age_4_5", "emotion_empathy"),
            ("age_4_5", "emotion_pride"),
            ("age_4_5", "emotion_disappointment"),
            ("age_4_5", "emotion_gratitude"),  # Added: learning thankfulness
            # Age 6-8: Complex emotional understanding
            ("age_6_8", "emotion_joy"),
            ("age_6_8", "emotion_curiosity"),
            ("age_6_8", "emotion_empathy"),
            ("age_6_8", "emotion_determination"),
            ("age_6_8", "emotion_pride"),
            ("age_6_8", "emotion_gratitude"),
            ("age_6_8", "emotion_patience"),
            ("age_6_8", "emotion_fear_mild"),
            ("age_6_8", "emotion_disappointment"),  # Added: can handle mild disappointment
            # Age 9-10: Full emotional range
            ("age_9_10", "emotion_joy"),
            ("age_9_10", "emotion_curiosity"),
            ("age_9_10", "emotion_empathy"),
            ("age_9_10", "emotion_determination"),
            ("age_9_10", "emotion_gratitude"),
            ("age_9_10", "emotion_patience"),
            ("age_9_10", "emotion_pride"),
            ("age_9_10", "emotion_fear_mild"),
            ("age_9_10", "emotion_disappointment"),  # Added: can handle disappointment maturely
            ("age_9_10", "emotion_surprise"),  # Added: appreciate unexpected twists
        ]
        
        for age, emotion in age_emotion_relations:
            self.add_edge(age, emotion, "appropriate_emotion_for_age")
        
        # Character -> Emotion (character_expresses)
        character_emotion_relations = [
            ("grandpa_tom", "emotion_patience"),
            ("grandpa_tom", "emotion_gratitude"),
            ("grandpa_tom", "emotion_pride"),
            ("emma", "emotion_curiosity"),
            ("emma", "emotion_joy"),
            ("emma", "emotion_determination"),
            ("emma", "emotion_empathy"),
            ("alex", "emotion_curiosity"),
            ("alex", "emotion_surprise"),
            ("alex", "emotion_joy"),
        ]
        
        for char, emotion in character_emotion_relations:
            self.add_edge(char, emotion, "character_expresses")
        
        # =============================================================================
        # 學習目標關係 (Learning Objective Relations)
        # =============================================================================
        
        # Theme -> Learning Objective (teaches_objective)
        theme_learning_relations = [
            ("sharing", "learning_sharing_cooperation"),
            ("sharing", "learning_empathy_development"),
            ("friendship", "learning_empathy_development"),
            ("friendship", "learning_sharing_cooperation"),
            ("honesty", "learning_emotional_regulation"),
            ("emotional_growth", "learning_emotional_regulation"),
            ("emotional_growth", "learning_empathy_development"),
            ("animals_exploration", "learning_basic_science_concepts"),
            ("animals_exploration", "learning_cause_effect"),
            ("puzzle_solving", "learning_problem_solving"),
            ("puzzle_solving", "learning_pattern_recognition"),
        ]
        
        for theme, learning in theme_learning_relations:
            self.add_edge(theme, learning, "teaches_objective")
        
        # Learning Objective -> Age Group (achievable_at_age)
        for learning_id, _, props in self.learning_objectives:
            learning_node_id = f"learning_{learning_id}"
            age_start = props.get("age_start", 2)
            age_end = props.get("age_end", 10)
            
            age_groups = [
                ("age_2_3", 2, 3),
                ("age_4_5", 4, 5),
                ("age_6_8", 6, 8),
                ("age_9_10", 9, 10),
            ]
            
            for age_id, age_min, age_max in age_groups:
                # 如果學習目標的年齡範圍與該年齡組有重疊
                if not (age_end < age_min or age_start > age_max):
                    self.add_edge(learning_node_id, age_id, "achievable_at_age")
        
        # =============================================================================
        # 節奏元素關係 (Pacing Element Relations)
        # =============================================================================
        
        # Theme -> Pacing (uses_pacing) - 簡化版，所有主題都能用全部節奏
        for theme_id, _, _ in self.themes:
            for pacing_id, _, _ in self.pacing_elements:
                self.add_edge(theme_id, f"pacing_{pacing_id}", "uses_pacing")
        
        # Pacing -> Age Group (pacing_fits_age) - 根據張力等級與認知能力分配
        pacing_age_map = {
            "gentle_intro": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],  # All ages benefit from gentle openings
            "curiosity_buildup": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],  # All ages enjoy gradual intrigue
            "surprise_moment": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],  # Changed: even toddlers love surprises
            "challenge_point": ["age_4_5", "age_6_8", "age_9_10"],  # Requires problem-solving ability
            "resolution_joy": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],  # All ages need positive resolution
            "peaceful_ending": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],  # All ages benefit from calm closure
            "reflection_moment": ["age_6_8", "age_9_10"],  # Requires metacognitive ability
        }
        
        for pacing, ages in pacing_age_map.items():
            for age in ages:
                self.add_edge(f"pacing_{pacing}", age, "pacing_fits_age")
        
        # =============================================================================
        # 角色成長弧線關係 (Character Arc Relations)
        # =============================================================================
        
        # Theme -> Character Arc (supports_arc)
        theme_arc_relations = [
            ("sharing", "arc_learning_to_share"),
            ("friendship", "arc_making_first_friend"),
            ("friendship", "arc_overcoming_shyness"),
            ("courage", "arc_gaining_confidence"),
            ("courage", "arc_standing_up_for_right"),
            ("emotional_growth", "arc_developing_patience"),
            ("emotional_growth", "arc_accepting_change"),
            ("honesty", "arc_standing_up_for_right"),
        ]
        
        for theme, arc in theme_arc_relations:
            self.add_edge(theme, arc, "supports_arc")
        
        # Character -> Character Arc (character_can_experience)
        character_arc_relations = [
            ("emma", "arc_gaining_confidence"),
            ("emma", "arc_discovering_talent"),
            ("emma", "arc_standing_up_for_right"),
            ("emma", "arc_developing_patience"),
            ("alex", "arc_learning_to_share"),
            ("alex", "arc_overcoming_shyness"),
            ("alex", "arc_making_first_friend"),
            ("grandpa_tom", "arc_accepting_change"),
        ]
        
        for char, arc in character_arc_relations:
            self.add_edge(char, arc, "character_can_experience")
        
        # =============================================================================
        # 文化元素關係 (Cultural Element Relations)
        # =============================================================================
        
        # Theme -> Cultural Element (involves_cultural_element)
        theme_cultural_relations = [
            ("traditions", "cultural_chinese_new_year"),
            ("traditions", "cultural_diwali"),
            ("traditions", "cultural_thanksgiving"),
            ("traditions", "cultural_mid_autumn_festival"),
            ("traditions", "cultural_storytelling_tradition"),
            ("traditions", "cultural_respect_for_elders"),
            ("inclusion", "cultural_respect_for_elders"),
            ("inclusion", "cultural_community_helping"),
            ("sharing", "cultural_community_helping"),
            ("friendship", "cultural_community_helping"),
        ]
        
        for theme, cultural in theme_cultural_relations:
            self.add_edge(theme, cultural, "involves_cultural_element")
        
        # Cultural Element -> Age Group (cultural_age_appropriate)
        cultural_age_map = {
            "storytelling_tradition": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],
            "respect_for_elders": ["age_2_3", "age_4_5", "age_6_8", "age_9_10"],
            "community_helping": ["age_4_5", "age_6_8", "age_9_10"],
            "chinese_new_year": ["age_4_5", "age_6_8", "age_9_10"],
            "diwali": ["age_4_5", "age_6_8", "age_9_10"],
            "thanksgiving": ["age_4_5", "age_6_8", "age_9_10"],
            "mid_autumn_festival": ["age_4_5", "age_6_8", "age_9_10"],
        }
        
        for cultural, ages in cultural_age_map.items():
            for age in ages:
                self.add_edge(f"cultural_{cultural}", age, "cultural_age_appropriate")
        
        # =============================================================================
        # 視覺風格關係 (Visual Style Relations)
        # =============================================================================
        
        # Category -> Visual Style (preferred_style)
        category_style_relations = [
            ("educational", "style_storybook_realistic"),
            ("educational", "style_bold_cartoon"),
            ("adventure", "style_whimsical_fantasy"),
            ("adventure", "style_bold_cartoon"),
            ("fun", "style_bold_cartoon"),
            ("cultural", "style_storybook_realistic"),
            ("environmental", "style_nature_inspired"),
            ("environmental", "style_storybook_realistic"),
            ("classic", "style_soft_watercolor"),
            ("classic", "style_storybook_realistic"),
        ]
        
        for category, style in category_style_relations:
            self.add_edge(category, style, "preferred_style")
        
        # Age Group -> Visual Style (age_appropriate_style)
        age_style_relations = [
            ("age_2_3", "style_soft_watercolor"),
            ("age_4_5", "style_soft_watercolor"),
            ("age_4_5", "style_bold_cartoon"),
            ("age_6_8", "style_bold_cartoon"),
            ("age_6_8", "style_storybook_realistic"),
            ("age_9_10", "style_storybook_realistic"),
            ("age_9_10", "style_whimsical_fantasy"),
        ]
        
        for age, style in age_style_relations:
            self.add_edge(age, style, "age_appropriate_style")

    # =============================================================================
    # 2. 核心圖操作 (Core Graph Operations)
    # =============================================================================

    def add_node(self, node_id: str, node_type: NodeType, label: str, properties: Dict):
        """添加節點"""
        node = KGNode(node_id, node_type, label, properties)
        self.nodes[node_id] = node
        
        # 同步到NetworkX - 避免參數衝突
        nx_properties = properties.copy()
        # 如果properties中有'type'鍵，重命名為'prop_type'避免與NetworkX的type參數衝突
        if 'type' in nx_properties:
            nx_properties['prop_type'] = nx_properties.pop('type')
        
        self.nx_graph.add_node(node_id, 
                              type=node_type.value, 
                              label=label, 
                              **nx_properties)
    
    def add_edge(self, source: str, target: str, relation: str, properties: Dict = None):
        """添加邊"""
        edge = KGEdge(source, target, relation, properties or {})
        self.edges.append(edge)
        
        # 同步到NetworkX
        self.nx_graph.add_edge(source, target, 
                              relation=relation, 
                              **(properties or {}))

    # =============================================================================
    # 3. 基礎查詢接口 (Basic Query Interface)
    # =============================================================================

    def query_by_type(self, node_type: NodeType) -> List[KGNode]:
        """按類型查詢節點"""
        return [node for node in self.nodes.values() if node.type == node_type]
    
    def find_related_nodes(self, node_id: str, relation: str = None) -> List[Tuple[str, str]]:
        """查找相關節點"""
        related = []
        for edge in self.edges:
            if edge.source == node_id:
                if relation is None or edge.relation == relation:
                    related.append((edge.target, edge.relation))
        return related

    def get_edges_by_relation(self, relation: str) -> List[KGEdge]:
        """獲取特定類型的所有關係邊 (First-class relation query)"""
        return [edge for edge in self.edges if edge.relation == relation]

    def get_targets_by_relation(self, source_id: str, relation: str) -> List[KGNode]:
        """獲取特定源節點和關係的所有目標節點"""
        target_ids = [edge.target for edge in self.edges 
                     if edge.source == source_id and edge.relation == relation]
        return [self.nodes[tid] for tid in target_ids if tid in self.nodes]

    def get_sources_by_relation(self, target_id: str, relation: str) -> List[KGNode]:
        """獲取特定目標節點和關係的所有源節點"""
        source_ids = [edge.source for edge in self.edges 
                     if edge.target == target_id and edge.relation == relation]
        return [self.nodes[sid] for sid in source_ids if sid in self.nodes]

    def query_edges(self, source_type: NodeType = None, relation: str = None, target_type: NodeType = None) -> List[KGEdge]:
        """
        通用邊查詢 - 支援基於節點類型和關係的組合查詢
        這使得關係成為可被獨立篩選的對象
        """
        result = []
        for edge in self.edges:
            # 檢查關係
            if relation and edge.relation != relation:
                continue
            
            # 檢查源節點類型
            if source_type:
                source_node = self.nodes.get(edge.source)
                if not source_node or source_node.type != source_type:
                    continue
            
            # 檢查目標節點類型
            if target_type:
                target_node = self.nodes.get(edge.target)
                if not target_node or target_node.type != target_type:
                    continue
            
            result.append(edge)
        return result

    # =============================================================================
    # 4. 進階推論與分析 (Advanced Inference & Analysis)
    # =============================================================================

    def infer_relations(self) -> int:
        """
        執行基於規則的圖推論
        不依賴硬編碼流程，而是基於圖結構產生新知識
        """
        new_edges = []
        
        # 規則 1: 適用性傳遞 (Transitivity of Suitability)
        # AgeGroup -> Category (suitable_for) AND Category -> Theme (contains_theme)
        # IMPLIES: AgeGroup -> Theme (suitable_for)
        
        # 獲取所有 suitable_for 關係
        suitable_edges = self.get_edges_by_relation("suitable_for")
        
        for edge1 in suitable_edges:
            # edge1: Age -> Category
            source_node = self.nodes.get(edge1.source)
            target_node = self.nodes.get(edge1.target)
            
            # 確保是 Age -> Category
            if source_node and source_node.type == NodeType.AGE_GROUP and \
               target_node and target_node.type == NodeType.CATEGORY:
                   
                # 查找 Category -> Theme 的 contains_theme 關係
                theme_edges = [e for e in self.edges 
                              if e.source == edge1.target and e.relation == "contains_theme"]
                
                for edge2 in theme_edges:
                    # 推論: Age -> Theme (suitable_for)
                    # 檢查是否已存在
                    exists = any(e.source == edge1.source and 
                               e.target == edge2.target and 
                               e.relation == "suitable_for" for e in self.edges + new_edges)
                    
                    if not exists:
                        new_edges.append(KGEdge(
                            source=edge1.source,
                            target=edge2.target,
                            relation="suitable_for",
                            properties={
                                "inferred": True, 
                                "rule": "transitivity_age_category_theme",
                                "confidence": 0.9
                            }
                        ))

        # 規則 2: 角色適用性反向推論 (Character Suitability Inference)
        # Character -> Category (appears_in)
        # IMPLIES: Category -> Character (has_character)
        
        appears_in_edges = self.get_edges_by_relation("appears_in")
        for edge in appears_in_edges:
             exists = any(e.source == edge.target and 
                          e.target == edge.source and 
                          e.relation == "has_character" for e in self.edges + new_edges)
             
             if not exists:
                 new_edges.append(KGEdge(
                     source=edge.target,
                     target=edge.source,
                     relation="has_character",
                     properties={
                         "inferred": True,
                         "rule": "inverse_appears_in",
                         "confidence": 1.0
                     }
                 ))

        # 規則 3: 概念驅動的主題支援推論 (Concept-driven subcategory -> theme)
        # Subcategory -> Concept (covers_concept) AND Theme -> Concept (involves_concept)
        # IMPLIES: Subcategory -> Theme (supports_theme)
        theme_concept_edges = self.get_edges_by_relation("involves_concept")
        subcat_concept_edges = self.get_edges_by_relation("covers_concept")

        # 建索引以降低 O(E^2)
        concept_to_themes: Dict[str, List[str]] = {}
        for e in theme_concept_edges:
            concept_to_themes.setdefault(e.target, []).append(e.source)

        for e in subcat_concept_edges:
            # e: SUBCATEGORY -> CONCEPT
            if e.target not in concept_to_themes:
                continue
            for theme_id in concept_to_themes[e.target]:
                exists = any(
                    ex.source == e.source and ex.target == theme_id and ex.relation == "supports_theme"
                    for ex in self.edges + new_edges
                )
                if exists:
                    continue
                new_edges.append(
                    KGEdge(
                        source=e.source,
                        target=theme_id,
                        relation="supports_theme",
                        properties={
                            "inferred": True,
                            "rule": "concept_overlap_subcategory_theme",
                            "confidence": 0.7,
                            "via_concept": e.target,
                        },
                    )
                )

        # 規則 4: 情感適用性傳遞 (Emotion Suitability Transitivity)
        # Theme -> Emotion (teaches_emotion) AND Age -> Emotion (appropriate_emotion_for_age)
        # IMPLIES: Age -> Theme (suitable_for) with higher confidence
        
        teaches_emotion_edges = self.get_edges_by_relation("teaches_emotion")
        appropriate_emotion_edges = self.get_edges_by_relation("appropriate_emotion_for_age")
        
        # 建立情感索引
        emotion_to_themes: Dict[str, List[str]] = {}
        for e in teaches_emotion_edges:
            emotion_to_themes.setdefault(e.target, []).append(e.source)
        
        for e in appropriate_emotion_edges:
            # e: AGE_GROUP -> EMOTION
            if e.target not in emotion_to_themes:
                continue
            for theme_id in emotion_to_themes[e.target]:
                # 檢查是否已有 age -> theme suitable_for
                exists = any(
                    ex.source == e.source and ex.target == theme_id and ex.relation == "suitable_for"
                    for ex in self.edges + new_edges
                )
                if exists:
                    continue
                new_edges.append(
                    KGEdge(
                        source=e.source,
                        target=theme_id,
                        relation="suitable_for",
                        properties={
                            "inferred": True,
                            "rule": "emotion_alignment_age_theme",
                            "confidence": 0.8,
                            "via_emotion": e.target,
                        },
                    )
                )

        # 規則 5: 學習目標反向推論 (Learning Objective Reverse Inference)
        # Theme -> Learning Objective (teaches_objective) AND Learning Objective -> Age (achievable_at_age)
        # IMPLIES: Age -> Theme (suitable_for)
        
        teaches_obj_edges = self.get_edges_by_relation("teaches_objective")
        achievable_edges = self.get_edges_by_relation("achievable_at_age")
        
        # 建立學習目標索引
        obj_to_themes: Dict[str, List[str]] = {}
        for e in teaches_obj_edges:
            obj_to_themes.setdefault(e.target, []).append(e.source)
        
        for e in achievable_edges:
            # e: LEARNING_OBJECTIVE -> AGE_GROUP
            if e.source not in obj_to_themes:
                continue
            for theme_id in obj_to_themes[e.source]:
                exists = any(
                    ex.source == e.target and ex.target == theme_id and ex.relation == "suitable_for"
                    for ex in self.edges + new_edges
                )
                if exists:
                    continue
                new_edges.append(
                    KGEdge(
                        source=e.target,
                        target=theme_id,
                        relation="suitable_for",
                        properties={
                            "inferred": True,
                            "rule": "learning_objective_age_theme",
                            "confidence": 0.85,
                            "via_objective": e.source,
                        },
                    )
                )

        # 批量添加推論出的邊
        count = 0
        for edge in new_edges:
            self.add_edge(edge.source, edge.target, edge.relation, edge.properties)
            count += 1
            
        return count

    def get_ontology(self) -> Dict[str, Any]:
        """回傳 KG 的 ontology / schema（供審查、導出或下游做安全檢查）。"""
        schema = {}
        for rel, (src_t, tgt_t) in self.RELATION_SCHEMA.items():
            schema[rel] = {
                "source_type": None if src_t is None else src_t.value,
                "target_type": None if tgt_t is None else tgt_t.value,
            }
        return {
            "schema_version": self.KG_SCHEMA_VERSION,
            "relation_schema": schema,
            "node_types": [t.value for t in NodeType],
        }

    def get_suitable_themes(
        self,
        age: int,
        category: str,
    ) -> List[Dict[str, Any]]:
        """查詢適合特定年齡和類別的主題列表（純查詢，不做決策）。
        
        Returns:
            List of dicts with keys: theme_id, label, priority ('high'|'medium'|'low')
            高優先級 = 年齡組直接適配的主題
            低優先級 = 只屬於該類別的主題
        """
        if category not in self.nodes:
            return []
        age_group = self._get_age_group_for_age(age)
        if not age_group:
            return []

        category_themes = [
            tid
            for tid, _ in self.find_related_nodes(category, "contains_theme")
            if tid in self.nodes and self.nodes[tid].type == NodeType.THEME
        ]
        if not category_themes:
            return []

        # suitable_for 可能同時連到 CATEGORY/THEME，這裡只取 THEME
        suitable_targets = self.get_targets_by_relation(age_group.id, "suitable_for")
        suitable_theme_ids = {n.id for n in suitable_targets if n and n.type == NodeType.THEME}
        
        results = []
        for tid in category_themes:
            theme_node = self.nodes[tid]
            priority = 'high' if tid in suitable_theme_ids else 'low'
            results.append({
                'theme_id': tid,
                'label': theme_node.label,
                'priority': priority,
                'properties': theme_node.properties
            })
        
        # 按優先級排序
        results.sort(key=lambda x: 0 if x['priority'] == 'high' else 1)
        return results

    def get_matching_subcategories(
        self,
        category: str,
        theme_id: str,
    ) -> List[Dict[str, Any]]:
        """查詢與主題匹配的子類別列表（純查詢，返回評分結果）。
        
        Returns:
            List of dicts sorted by score (descending), each containing:
            - subcategory_id: str
            - subcategory_node_id: str  
            - label: str
            - score: int
            - reasons: List[str]
            - overlap_concepts: List[str]
        """
        if category not in self.nodes or theme_id not in self.nodes:
            return []

        subcats = [
            n
            for n in self.get_targets_by_relation(category, "has_subcategory")
            if n and n.type == NodeType.SUBCATEGORY
        ]
        if not subcats:
            return []

        theme_concepts = {
            n.id
            for n in self.get_targets_by_relation(theme_id, "involves_concept")
            if n and n.type == NodeType.CONCEPT
        }

        results = []
        for sub in subcats:
            score = 0
            reasons: List[str] = []

            # 1) 直接 supports_theme
            direct = any(
                e.source == sub.id and e.target == theme_id and e.relation == "supports_theme" for e in self.edges
            )
            if direct:
                score += 5
                reasons.append("direct_supports_theme")

            # 2) 概念重疊
            sub_concepts = {
                n.id
                for n in self.get_targets_by_relation(sub.id, "covers_concept")
                if n and n.type == NodeType.CONCEPT
            }
            overlap = sorted(theme_concepts.intersection(sub_concepts))
            if overlap:
                score += 2 * len(overlap)
                reasons.append(f"concept_overlap:{len(overlap)}")

            subcategory_id = sub.properties.get("subcategory_id")
            results.append({
                "subcategory_node_id": sub.id,
                "subcategory_id": subcategory_id if isinstance(subcategory_id, str) else None,
                "label": sub.label,
                "score": score,
                "reasons": reasons,
                "overlap_concepts": [self.nodes[c].label for c in overlap if c in self.nodes],
            })

        # 按分數排序（降序）
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # =============================================================================
    # 5. 故事配置邏輯 (Story Configuration Logic)
    # =============================================================================

    def get_subgraph(self, center_id: str, depth: int = 1) -> Dict[str, Any]:
        """
        獲取以特定節點為中心的子圖 (Pure Knowledge Access)
        這證明了知識可以脫離生成流程獨立存在
        """
        if center_id not in self.nodes:
            return {"error": "Node not found"}
            
        sub_nodes = {center_id: self.nodes[center_id]}
        sub_edges = []
        
        current_level_ids = {center_id}
        
        for _ in range(depth):
            next_level_ids = set()
            for edge in self.edges:
                if edge.source in current_level_ids:
                    sub_nodes[edge.target] = self.nodes.get(edge.target)
                    sub_edges.append(edge)
                    next_level_ids.add(edge.target)
                elif edge.target in current_level_ids:
                    sub_nodes[edge.source] = self.nodes.get(edge.source)
                    sub_edges.append(edge)
                    next_level_ids.add(edge.source)
            current_level_ids = next_level_ids
            
        return {
            "center": center_id,
            "nodes": [asdict(n) for n in sub_nodes.values() if n],
            "edges": [asdict(e) for e in sub_edges]
        }

    # =============================================================================
    # 5. 故事配置邏輯 (Story Configuration Logic)
    # =============================================================================

    def get_story_config(self, age: int, category: str, include_variations: bool = True) -> Dict[str, Any]:
        """獲取故事配置 - 核心查詢功能，包含完整變化系統"""
        
        # 1. 確定年齡組
        age_group = self._get_age_group_for_age(age)
        if not age_group:
            return {"error": "Invalid age"}
        
        # 2. 獲取年齡配置
        age_config = age_group.properties
        
        # 3. 獲取類別詳細配置
        category_node = self.nodes.get(category)
        if not category_node:
            return {"error": f"Category '{category}' not found"}
        
        category_config = category_node.properties
        
        # 4. 獲取類別主題 (增強版：包含情感、學習目標、文化元素)
        themes = self.find_related_nodes(category, "contains_theme")
        theme_details = {}
        for theme_id, _ in themes:
            theme_node = self.nodes[theme_id]
            
            # 獲取關聯的豐富元數據
            related_emotions = [
                self.nodes[n.id].label 
                for n in self.get_targets_by_relation(theme_id, "teaches_emotion") 
                if n.type == NodeType.EMOTION
            ]
            
            related_objectives = [
                self.nodes[n.id].label 
                for n in self.get_targets_by_relation(theme_id, "teaches_objective") 
                if n.type == NodeType.LEARNING_OBJECTIVE
            ]
            
            related_cultural = [
                self.nodes[n.id].label 
                for n in self.get_targets_by_relation(theme_id, "involves_cultural_element") 
                if n.type == NodeType.CULTURAL_ELEMENT
            ]
            
            theme_details[theme_id] = {
                "label": theme_node.label,
                "properties": theme_node.properties,
                "related_emotions": related_emotions,
                "related_objectives": related_objectives,
                "related_cultural": related_cultural
            }
        
        # 5. 獲取適合角色
        characters = []
        character_details = {}
        for char_id, char in self.nodes.items():
            if char.type == NodeType.CHARACTER:
                char_relations = self.find_related_nodes(char_id, "appears_in")
                if any(rel_target == category for rel_target, _ in char_relations):
                    characters.append(char.label)
                    character_details[char_id] = {
                        "label": char.label,
                        "properties": char.properties
                    }
        
        config = {
            "age_group": age_group.label,
            "age_group_id": age_group.id,
            "age_config": age_config,
            "category": category_node.label,
            "category_id": category,
            "category_config": category_config,
            "themes": theme_details,
            "characters": character_details,
            "timestamp": pd.Timestamp.now().isoformat(),
            "kg_version": "StoryGenerationKG-1.0",
        }
        
        # 6. 添加變化元素（如果請求）
        if include_variations:
            variations = self._get_story_variations(category, age)
            config["variations"] = variations
        
        # 7. 添加知識增強與適配規則
        config["knowledge_enhancement"] = self._get_knowledge_enhancement(category, age_group.label)
        config["adaptation_rules"] = category_config.get("adaptation_rules", {})
        
        return config
    
    def get_random_story_config(self, age: int, category: str = None, rng: Optional[random.Random] = None) -> Dict[str, Any]:
        """獲取隨機故事配置"""
        
        roller = self._get_rng(rng)

        # 如果沒有指定類別，隨機選擇一個適合的類別
        if not category:
            suitable_categories = []
            age_group = self._get_age_group_for_age(age)
            if age_group:
                age_group_id = age_group.id
                for cat_id, cat_node in self.nodes.items():
                    if cat_node.type == NodeType.CATEGORY:
                        # 檢查年齡組是否適合這個類別
                        age_relations = self.find_related_nodes(age_group_id, "suitable_for")
                        if any(rel_target == cat_id for rel_target, _ in age_relations):
                            suitable_categories.append(cat_id)
            
            if suitable_categories:
                category = roller.choice(suitable_categories)
            else:
                category = "educational"  # 默認選擇
        
        # 獲取基本配置
        config = self.get_story_config(age, category, include_variations=True)

        # 推薦一個更一致的主題（供下游使用；不破壞既有 themes 結構）
        # 使用純查詢方法 get_suitable_themes 獲取候選列表，再進行隨機選擇
        suitable_themes = self.get_suitable_themes(age, category)
        selected_theme_id = None
        
        if suitable_themes:
            # 優先選擇高優先級的主題
            high_priority = [t for t in suitable_themes if t['priority'] == 'high']
            if high_priority:
                selected_theme_id = roller.choice(high_priority)['theme_id']
            else:
                selected_theme_id = roller.choice(suitable_themes)['theme_id']
        
        # 如果沒有找到適合的主題（極少見），從配置中隨機選一個
        if not selected_theme_id and config.get("themes"):
            selected_theme_id = roller.choice(list(config["themes"].keys()))

        if selected_theme_id and selected_theme_id in (config.get("themes") or {}):
            config["selected_theme_id"] = selected_theme_id
            config["selected_theme"] = self.nodes[selected_theme_id].label if selected_theme_id in self.nodes else selected_theme_id
        
        # 隨機選擇變化元素
        if "variations" in config:
            variations = config["variations"]

            selection_trace: Dict[str, Any] = {}
            
            # 隨機選擇故事結構
            if variations["story_structures"]:
                config["selected_structure"] = roller.choice(variations["story_structures"])
                selection_trace["structure"] = {
                    "id": config["selected_structure"].get("id"),
                    "label": config["selected_structure"].get("label"),
                    "note": "filtered_by_KG_relation(structure_suitable_for) then sampled",
                }
            
            # 隨機選擇角色動態
            if variations["character_dynamics"]:
                config["selected_dynamic"] = roller.choice(variations["character_dynamics"])
                selection_trace["dynamic"] = {
                    "id": config["selected_dynamic"].get("id"),
                    "label": config["selected_dynamic"].get("label"),
                    "note": "filtered_by_KG_relation(dynamic_suitable_for_age) then sampled",
                }
            
            # 隨機選擇故事催化劑
            if variations["story_catalysts"]:
                config["selected_catalyst"] = roller.choice(variations["story_catalysts"])
                selection_trace["catalyst"] = {
                    "id": config["selected_catalyst"].get("id"),
                    "label": config["selected_catalyst"].get("label"),
                    "note": "filtered_by_KG_relation(catalyst_fits_category) then sampled",
                }
            
            # 隨機選擇類別特定元素
            if variations["category_specific"]:
                # 優先使用 theme 一致性的推薦 subcategory（若有 selected_theme_id）
                subcategory = None
                sub_explain = None
                
                if isinstance(selected_theme_id, str):
                    # 使用純查詢方法 get_matching_subcategories
                    matching_subcats = self.get_matching_subcategories(category, selected_theme_id)
                    if matching_subcats:
                        # 選擇分數最高的
                        max_score = matching_subcats[0]['score']
                        best_matches = [s for s in matching_subcats if s['score'] == max_score]
                        chosen = roller.choice(best_matches)
                        subcategory = chosen['subcategory_id']
                        sub_explain = {"reason": "high_match_score", "score": max_score, "details": chosen['reasons']}

                if not subcategory or subcategory not in variations["category_specific"]:
                    # 如果沒有匹配的子類別，隨機選擇一個
                    available_subcats = list(variations["category_specific"].keys())
                    if available_subcats:
                        subcategory = roller.choice(available_subcats)
                        sub_explain = {"reason": "fallback_random_choice"}

                if subcategory:
                    config["selected_subcategory"] = subcategory
                    config["subcategory_config"] = variations["category_specific"][subcategory]
                    selection_trace["subcategory"] = {"selected": subcategory, "explain": sub_explain}

            if selection_trace:
                config["selection_trace"] = selection_trace
        
        return config

    def _get_story_variations(self, category: str, age: int) -> Dict[str, Any]:
        """獲取故事變化元素 - 基於圖譜關係進行智能篩選"""
        
        variations = {
            "story_structures": [],
            "character_dynamics": [],
            "story_catalysts": [],
            "category_specific": {}
        }
        
        # 獲取當前年齡組ID
        age_group = self._get_age_group_for_age(age)
        age_group_id = age_group.id if age_group else None
        
        # 獲取通用變化元素
        for node_id, node in self.nodes.items():
            if node.type == NodeType.GENERATION_PARAM:
                param_type = node.properties.get("type")
                
                # 1. 篩選故事結構 (基於類別)
                if param_type == "story_structure":
                    # 檢查是否有類別約束
                    constraints = self.get_targets_by_relation(node_id, "structure_suitable_for")
                    # 如果沒有約束(通用) 或 當前類別在約束列表中 -> 納入
                    if not constraints or any(c.id == category for c in constraints):
                        variations["story_structures"].append({
                            "id": node_id,
                            "label": node.label,
                            "type": node.properties.get("variation_type"),
                            "description": node.properties.get("description")
                        })
                        
                # 2. 篩選角色動態 (基於年齡)
                elif param_type == "character_dynamic":
                    # 檢查是否有年齡約束
                    constraints = self.get_targets_by_relation(node_id, "dynamic_suitable_for_age")
                    # 如果沒有約束(通用) 或 當前年齡組在約束列表中 -> 納入
                    if not constraints or (age_group_id and any(c.id == age_group_id for c in constraints)):
                        variations["character_dynamics"].append({
                            "id": node_id,
                            "label": node.label,
                            "type": node.properties.get("variation_type"),
                            "description": node.properties.get("description")
                        })
                        
                # 3. 篩選催化劑 (基於類別)
                elif param_type == "story_catalyst":
                    # 檢查是否有類別約束
                    constraints = self.get_targets_by_relation(node_id, "catalyst_fits_category")
                    # 如果沒有約束(通用) 或 當前類別在約束列表中 -> 納入
                    if not constraints or any(c.id == category for c in constraints):
                        variations["story_catalysts"].append({
                            "id": node_id,
                            "label": node.label,
                            "type": node.properties.get("variation_type"),
                            "description": node.properties.get("description")
                        })
        
        # 獲取類別特定的變化（優先使用子類別節點，維持與既有介面相容：dict[subcat_id] -> config）
        category_specific: Dict[str, Any] = {}
        for edge in self.edges:
            if edge.source == category and edge.relation == "has_subcategory":
                sub_node = self.nodes.get(edge.target)
                if sub_node and sub_node.type == NodeType.SUBCATEGORY:
                    subcat_id = sub_node.properties.get("subcategory_id")
                    subcfg = (sub_node.properties.get("config") or {})
                    if isinstance(subcat_id, str):
                        category_specific[subcat_id] = subcfg

        if not category_specific:
            category_node = self.nodes.get(category)
            if category_node and "subcategories" in category_node.properties:
                variations["category_specific"] = category_node.properties["subcategories"]
        else:
            variations["category_specific"] = category_specific
        
        return variations

    def _get_knowledge_enhancement(self, category: str, age_label: str) -> str:
        """獲取知識庫增強內容"""
        enhancements = {
            "educational": {
                "Age 2-3": "Learning Focus: Basic concepts, colors, numbers, simple words",
                "Age 4-5": "Learning Focus: Interactive learning, simple problem-solving, basic skills",
                "Age 6-8": "Learning Focus: Problem-solving, character development, emotional learning",
                "Age 9-10": "Learning Focus: Critical thinking, complex concepts, deeper understanding"
            },
            "adventure": {
                "Age 2-3": "Adventure Style: Safe exploration, gentle challenges, friendly environments",
                "Age 4-5": "Adventure Style: Gentle exploration, simple challenges, safe discoveries",
                "Age 6-8": "Adventure Style: Moderate challenges, problem-solving, teamwork",
                "Age 9-10": "Adventure Style: Engaging challenges, character growth, meaningful outcomes"
            },
            "fun": {
                "Age 2-3": "Fun Style: Simple humor, familiar situations, gentle laughter",
                "Age 4-5": "Fun Style: Playful humor, amusing scenarios, joyful moments",
                "Age 6-8": "Fun Style: Creative humor, clever situations, entertaining adventures",
                "Age 9-10": "Fun Style: Sophisticated humor, witty scenarios, engaging entertainment"
            }
        }
        
        cat_enhancements = enhancements.get(category, {})
        # 嘗試精確匹配
        if age_label in cat_enhancements:
            return cat_enhancements[age_label]
        
        # 嘗試模糊匹配
        for key, value in cat_enhancements.items():
            if key in age_label:
                return value
                
        return "Create engaging and appropriate content for the story type and age group"

    # =============================================================================
    # 6. 年齡與內容工具 (Age & Content Utilities)
    # =============================================================================

    def _get_age_group_for_age(self, age: int) -> Optional[KGNode]:
        """根據年齡獲取年齡組"""
        for node in self.nodes.values():
            if node.type == NodeType.AGE_GROUP:
                if node.properties["min_age"] <= age <= node.properties["max_age"]:
                    return node
        return None
    
    def get_layout_config(self, age_value: int) -> Dict[str, Any]:
        """Get layout configuration for specific age."""
        age_node = self._get_age_group_for_age(age_value)
        if age_node:
            return age_node.properties.get("layout_config", {})
        return {}
    
    def get_word_ranges(self, age_value: int) -> Dict[str, Tuple[int, int]]:
        """Get word ranges for different page types."""
        age_node = self._get_age_group_for_age(age_value)
        if age_node:
            return age_node.properties.get("word_ranges", {})
        return {"narrative": (60, 100), "turning_point": (120, 160), "post_branch": (100, 140)}
    
    def get_interaction_rules(self, age_value: int) -> Dict[str, Any]:
        """Get interaction rules for specific age."""
        age_node = self._get_age_group_for_age(age_value)
        if age_node:
            return age_node.properties.get("interaction_rules", {})
        return {"has_interaction": False, "turning_point_only": True}
    
    def get_age_specific_config(self, age_input: str) -> Dict[str, Any]:
        """
        獲取年齡特定的配置信息，包含詳細的用字和品質要求
        
        Args:
            age_input: 年齡輸入，如 "2-3", "5", "6-8" 等
            
        Returns:
            包含年齡特定配置的字典
        """
        # Try to parse string input to int
        try:
            if isinstance(age_input, int):
                val = age_input
            elif "-" in age_input:
                # Handle "2-3" -> take average or start? _get_age_group_for_age takes int.
                # Let's take the start of the range.
                val = int(age_input.split("-")[0])
            else:
                val = int(age_input)
        except:
            val = 5 # Default fallback

        node = self._get_age_group_for_age(val)
        if node:
            return node.properties
        
        # Fallback if no node found
        return {
            "age_group": str(age_input),
            "language_guidelines": "Use simple language.",
            "vocabulary_level": "basic"
        }
        
    def get_layout_for_age(self, age_value: int, seed: Optional[int] = None, layout_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves a layout template STRICTLY.
        
        Rules:
        1. If layout_id provided: MUST exist.
        2. Else:
            - Age 2-3 => 'linear_4'
            - Age 4-5 => 'std_16'
            - Age 6-8 => 'std_20'
            - Other => Error (or strictly defined mapped default)

        NO RANDOM SELECTION. NO GENERIC FALLBACKS.
        """
        node = self._get_age_group_for_age(age_value)
        if not node:
            raise ValueError(f"CRITICAL: No knowledge graph node defined for Age {age_value}")

        templates = node.properties.get("layout_templates", [])
        if not templates:
            raise ValueError(f"CRITICAL: No layout templates defined for Age {age_value}")

        # 1. Determine Target ID
        target_id = layout_id
        if not target_id:
            if age_value <= 3:
                target_id = "linear_4"
            elif 4 <= age_value <= 5:
                target_id = "std_16"
            elif 6 <= age_value <= 8:
                target_id = "std_20"
            elif 9 <= age_value <= 10:
                target_id = "adv_20"
            else:
                target_id = "std_20" # Fallback 

        # 2. Fetch Strictly
        for t in templates:
            if t["id"] == target_id:
                return t

        # 3. Fail if not found
        raise ValueError(f"CRITICAL: Required layout '{target_id}' not found in templates for Age {age_value}. Available: {[t['id'] for t in templates]}")

    
    def get_text_quality_requirements(self, age_input: str) -> Dict[str, Any]:
        """
        獲取特定年齡的文本品質要求
        
        Args:
            age_input: 年齡輸入
            
        Returns:
            文本品質要求字典
        """
        age_config = self.get_age_specific_config(age_input)
        
        return {
            "character_naming": age_config.get("character_naming", {}),
            "grammar_requirements": age_config.get("grammar_requirements", {}),
            "content_consistency": age_config.get("content_consistency", {}),
            "language_guidelines": age_config.get("language_guidelines", ""),
            "vocabulary_level": age_config.get("vocabulary_level", "basic"),
            "sentence_structure": age_config.get("sentence_structure", "simple")
        }
    
    def get_enhanced_prompt_guidelines(self, age: str, category: str) -> str:
        """
        獲取增強的提示詞指導（基於用戶反饋改進）
        專門解決角色名稱不統一、拼寫錯誤、年齡適應性等問題
        """
        age_config = self.get_age_specific_config(age)
        
        # 獲取標準角色名稱
        character_examples = age_config.get("character_naming", {}).get("examples", ["Emma", "Grandpa Tom", "Alex"])
        
        # 構建詳細的品質要求
        guidelines = f"""
CRITICAL QUALITY REQUIREMENTS FOR AGE {age}:

1. CHARACTER NAMES - ABSOLUTE CONSISTENCY REQUIRED:
   - MUST use EXACTLY these names: {', '.join(character_examples)}
   - NO variations, abbreviations, or spelling changes allowed
   - Examples: 
     CORRECT: "Emma", "Grandpa Tom", "Alex"
     WRONG: "Little Emma", "Little Alex", "Emma-Girl", "Alexander", "Tom"

2. SPELLING & GRAMMAR - PERFECT ENGLISH REQUIRED:
   - Check every "a" vs "an": "a story" (correct), "an adventure" (correct)
   - NO typos: "animally"→"magically", "amulect"→"amulet", "readyto"→"ready to"
   - NO foreign characters: Use only standard English alphabet

3. PAGE FORMAT - EXACT STANDARD:
   - Format: "Page X:" (where X is the page number)
   - NO variations like "Page 1:3", "Page &#x2032;8", or Chinese characters

4. SENTENCE LENGTH for {age}:
   - {age_config.get("grammar_requirements", {}).get("sentence_length", "8-12 words recommended")}
   - Keep language appropriate for {age} year olds

5. PUNCTUATION - ENGLISH ONLY:
   - Use: . , ! ? " ' ( )
   - NO Chinese punctuation: ，。？！

6. CONTENT CONSISTENCY:
   - {age_config.get("content_consistency", {}).get("character_behavior", "Maintain consistent character behavior")}
   - {age_config.get("content_consistency", {}).get("plot_structure", "Ensure logical plot flow")}

7. ENCODING STANDARDS:
   - Standard English characters only
   - NO HTML entities, special symbols, or mixed alphabets

DOUBLE-CHECK: Review every character name, spelling, and punctuation before finalizing.
PRIORITY: Character name consistency is the most critical requirement.
"""
        
        return guidelines.strip()
    
    def validate_story_content(self, content: str, age: str, category: str) -> Dict[str, Any]:
        """
        使用KG配置驗證故事內容品質
        """
        age_config = self.get_age_specific_config(age)
        issues = []
        suggestions = []
        
        # 檢查字數限制
        word_limit = age_config.get("word_limit", (50, 100))
        word_count = len(content.split())
        
        if word_count < word_limit[0]:
            issues.append(f"內容過短: {word_count}字，建議{word_limit[0]}字以上")
        elif word_count > word_limit[1] * 1.5:  # 允許50%容差
            suggestions.append(f"內容較長: {word_count}字，建議控制在{word_limit[1]}字內")
        
        # 檢查頁面數量
        page_range = age_config.get("page_range", (8, 12))
        pages = len(re.findall(r'Page\s*\d+:', content))
        
        if pages < page_range[0]:
            issues.append(f"頁面過少: {pages}頁，建議{page_range[0]}頁以上")
        elif pages > page_range[1]:
            suggestions.append(f"頁面較多: {pages}頁，建議控制在{page_range[1]}頁內")
        
        # 檢查複雜度
        complexity = age_config.get("complexity", "basic")
        avoid_words = age_config.get("character_naming", {}).get("avoid", [])
        
        found_complex = []
        for word in avoid_words:
            if word in content.lower():
                found_complex.append(word)
        
        if found_complex:
            issues.append(f"發現不適合{age}歲的詞彙: {found_complex}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "word_count": word_count,
            "page_count": pages,
            "complexity_check": len(found_complex) == 0
        }

    def is_common_word(self, word: str) -> bool:
        """檢查是否為常見非角色詞"""
        common_words = {
            'The', 'This', 'That', 'Here', 'There', 'Now', 'Then', 'When', 'Where',
            'What', 'Who', 'Why', 'How', 'Yes', 'No', 'And', 'But', 'Or', 'So',
            'Today', 'Tomorrow', 'Yesterday', 'Page', 'Chapter', 'Story', 'Book',
            'Magic', 'Magical', 'Beautiful', 'Wonderful', 'Amazing', 'Special'
        }
        return word in common_words
    
    def identify_scene_type(self, content: str) -> str:
        """智能識別場景類型"""
        if not content:
            return "general"
            
        content_lower = content.lower()
        
        # 定義場景類型關鍵詞映射
        scene_keywords = {
            "outdoor": {
                "keywords": ['outside', 'garden', 'park', 'forest', 'tree', 'grass', 'sky', 'sun', 'moon', 'nature', 'field', 'mountain', 'beach', 'river'],
                "weight": 0
            },
            "indoor": {
                "keywords": ['home', 'house', 'room', 'kitchen', 'bedroom', 'living', 'inside', 'door', 'window', 'table', 'chair', 'bed', 'wall'],
                "weight": 0
            },
            "magical": {
                "keywords": ['magic', 'magical', 'spell', 'wand', 'fairy', 'wizard', 'enchanted', 'mystical', 'potion', 'crystal', 'sparkle', 'glow'],
                "weight": 0
            },
            "educational": {
                "keywords": ['learn', 'teach', 'lesson', 'school', 'study', 'book', 'read', 'write', 'discover', 'explore', 'understand'],
                "weight": 0
            },
            "adventure": {
                "keywords": ['adventure', 'journey', 'explore', 'discover', 'find', 'search', 'quest', 'treasure', 'mystery', 'exciting'],
                "weight": 0
            },
            "family": {
                "keywords": ['family', 'together', 'love', 'care', 'share', 'help', 'hug', 'grandpa', 'grandma', 'parent', 'child'],
                "weight": 0
            },
            "emotional": {
                "keywords": ['happy', 'sad', 'excited', 'worried', 'surprised', 'amazed', 'proud', 'grateful', 'thoughtful', 'gentle'],
                "weight": 0
            }
        }
        
        # 計算每種場景類型的權重
        for scene_type, data in scene_keywords.items():
            for keyword in data["keywords"]:
                # 完全匹配獲得更高權重
                if f" {keyword} " in f" {content_lower} ":
                    data["weight"] += 2
                # 部分匹配獲得較低權重
                elif keyword in content_lower:
                    data["weight"] += 1
        
        # 特殊模式檢測
        # 對話場景
        if content.count('"') >= 2:
            scene_keywords["dialogue"] = {"weight": 3}
        
        # 動作場景
        action_words = ['walked', 'ran', 'jumped', 'moved', 'went', 'came', 'opened', 'closed']
        action_count = sum(1 for word in action_words if word in content_lower)
        if action_count >= 2:
            scene_keywords["action"] = {"weight": action_count * 2}
        
        # 找出權重最高的場景類型
        max_weight = 0
        best_scene = "general"
        
        for scene_type, data in scene_keywords.items():
            if data["weight"] > max_weight:
                max_weight = data["weight"]
                best_scene = scene_type
        
        return best_scene if max_weight > 0 else "general"
    
    def adjust_for_age_appropriateness(self, text: str, age: str) -> str:
        """根據年齡調整內容複雜度"""
        if not text:
            return text
            
        # 獲取年齡組配置
        age_config = self.get_age_specific_config(age)
        
        if not age_config:
            return text
        
        # 根據年齡調整詞彙複雜度
        if age in ["2-3", "4-5"]:
            # 簡化複雜詞彙
            simple_replacements = {
                r'\bdiscover(ed|ing)?\b': 'find',
                r'\bexplor(e|ed|ing)\b': 'look around',
                r'\brealize(d|s)?\b': 'know',
                r'\bdetermined\b': 'sure',
                r'\bmagnificent\b': 'beautiful',
                r'\benormous\b': 'very big',
                r'\btiny\b': 'very small',
                r'\bimmediately\b': 'right away',
                r'\bcarefully\b': 'slowly',
            }
            
            import re
            for pattern, replacement in simple_replacements.items():
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # 句子長度檢查（年齡適宜）
        import re
        sentences = re.split(r'[.!?]+', text)
        adjusted_sentences = []
        
        max_words = {
            "2-3": 8,
            "4-5": 12,
            "6-8": 16,
            "9-10": 20
        }.get(age, 16)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                words = sentence.split()
                if len(words) > max_words:
                    # 分割長句子
                    mid_point = len(words) // 2
                    first_part = " ".join(words[:mid_point])
                    second_part = " ".join(words[mid_point:])
                    adjusted_sentences.extend([first_part, second_part])
                else:
                    adjusted_sentences.append(sentence)
        
        return '. '.join(adjusted_sentences) + '.' if adjusted_sentences else text

    # =============================================================================
    # 7. 會話管理 (Session Management)
    # =============================================================================
    
    def create_generation_session(self, session_id: str, config: Dict) -> str:
        """創建生成會話"""
        session_node_id = f"session_{session_id}"
        
        self.add_node(
            session_node_id,
            NodeType.STORY_STATE,
            f"Generation Session {session_id}",
            {
                "session_id": session_id,
                "config": config,
                "status": "initialized",
                "created_at": pd.Timestamp.now().isoformat(),
                "pages_generated": 0,
                "current_themes": [],
                "character_states": {}
            }
        )
        
        return session_node_id
    
    def update_generation_state(self, session_id: str, updates: Dict):
        """更新生成狀態"""
        session_node_id = f"session_{session_id}"
        if session_node_id in self.nodes:
            self.nodes[session_node_id].properties.update(updates)
            self.nodes[session_node_id].properties["updated_at"] = pd.Timestamp.now().isoformat()
    
    def get_generation_history(self) -> List[Dict]:
        """獲取生成歷史"""
        sessions = []
        for node in self.nodes.values():
            if node.type == NodeType.STORY_STATE:
                sessions.append({
                    "session_id": node.properties.get("session_id"),
                    "created_at": node.properties.get("created_at"),
                    "status": node.properties.get("status"),
                    "pages_generated": node.properties.get("pages_generated", 0)
                })
        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)
    
    # =============================================================================
    # 8. 可視化與導出 (Visualization & Export)
    # =============================================================================
    
    def visualize_full_graph(self, height=800, width=1200):
        """可視化完整知識圖譜"""
        
        # 使用NetworkX計算布局
        pos = nx.spring_layout(self.nx_graph, k=3, iterations=50)
        
        # 準備節點數據
        node_trace_data = {node_type: {"x": [], "y": [], "text": [], "ids": []} 
                          for node_type in NodeType}
        
        # 節點顏色映射
        colors = {
            NodeType.AGE_GROUP: "#FF6B6B",
            NodeType.CATEGORY: "#4ECDC4", 
            NodeType.SUBCATEGORY: "#00B894",
            NodeType.THEME: "#45B7D1",
            NodeType.CHARACTER: "#96CEB4",
            NodeType.SCENE: "#74B9FF",
            NodeType.CONCEPT: "#A29BFE",
            NodeType.STORY_STATE: "#FFEAA7",
            NodeType.GENERATION_PARAM: "#DDA0DD",
            NodeType.EMOTION: "#FF85C0",
            NodeType.LEARNING_OBJECTIVE: "#FFD93D",
            NodeType.PACING_ELEMENT: "#6BCB77",
            NodeType.CHARACTER_ARC: "#F38181",
            NodeType.CULTURAL_ELEMENT: "#C780FA",
            NodeType.VISUAL_STYLE: "#95E1D3",
            NodeType.RELATIONSHIP: "#FDCB6E",
        }
        
        for node_id, (x, y) in pos.items():
            node = self.nodes[node_id]
            node_type = node.type
            
            node_trace_data[node_type]["x"].append(x)
            node_trace_data[node_type]["y"].append(y)
            node_trace_data[node_type]["text"].append(f"{node.label}<br>ID: {node_id}")
            node_trace_data[node_type]["ids"].append(node_id)
        
        # 準備邊數據
        edge_x, edge_y = [], []
        edge_info = []
        
        for edge in self.edges:
            if edge.source in pos and edge.target in pos:
                x0, y0 = pos[edge.source]
                x1, y1 = pos[edge.target]
                
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
                edge_info.append(f"{edge.source} → {edge.target} ({edge.relation})")
        
        # 創建圖形
        fig = go.Figure()
        
        # 添加邊
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            mode='lines',
            line=dict(width=1, color='#888'),
            hoverinfo='none',
            showlegend=False,
            name='關係'
        ))
        
        # 添加節點（按類型分組）
        for node_type, data in node_trace_data.items():
            if data["x"]:  # 只添加有數據的類型
                fig.add_trace(go.Scatter(
                    x=data["x"], y=data["y"],
                    mode='markers+text',
                    marker=dict(
                        size=20,
                        color=colors[node_type],
                        line=dict(width=2, color='white')
                    ),
                    text=[text.split('<br>')[0] for text in data["text"]],  # 只顯示標籤
                    textposition="middle center",
                    hovertext=data["text"],
                    hoverinfo='text',
                    name=node_type.value.replace('_', ' ').title(),
                    customdata=data["ids"]
                ))
        
        fig.update_layout(
            title="故事生成知識圖譜",
            showlegend=True,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                text="節點類型：年齡組、類別、子類別、主題、角色、場景、概念、生成狀態",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002,
                xanchor='left', yanchor='bottom',
                font=dict(color='gray', size=12)
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=height,
            width=width
        )
        
        return fig
    
    def visualize_generation_stats(self):
        """可視化生成統計信息"""
        
        # 獲取統計數據
        stats = self._compute_stats()
        
        # 創建子圖
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Node Type Distribution", "Generation Session Stats", "Age Group Coverage", "Category Theme Relations"),
            specs=[[{"type": "pie"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        # 1. 節點類型分佈
        node_types = list(stats["node_distribution"].keys())
        node_counts = list(stats["node_distribution"].values())
        
        fig.add_trace(
            go.Pie(labels=node_types, values=node_counts, name="Node Distribution"),
            row=1, col=1
        )
        
        # 2. 生成會話統計
        sessions = self.get_generation_history()
        if sessions:
            session_status = {}
            for session in sessions:
                status = session["status"]
                session_status[status] = session_status.get(status, 0) + 1
            
            fig.add_trace(
                go.Bar(x=list(session_status.keys()), y=list(session_status.values()), name="Session Status"),
                row=1, col=2
            )
        
        # 3. 年齡組覆蓋率
        age_groups = [node.label for node in self.nodes.values() if node.type == NodeType.AGE_GROUP]
        coverage = [len(self.find_related_nodes(f"age_{ag.split(' ')[1].replace('-', '_')}", "suitable_for")) 
                   for ag in age_groups]
        
        fig.add_trace(
            go.Bar(x=age_groups, y=coverage, name="Applicable Categories"),
            row=2, col=1
        )
        
        # 4. 類別主題關係網絡
        categories = [node for node in self.nodes.values() if node.type == NodeType.CATEGORY]
        for i, cat in enumerate(categories):
            themes = self.find_related_nodes(cat.id, "contains_theme")
            fig.add_trace(
                go.Scatter(
                    x=[i] * len(themes), 
                    y=list(range(len(themes))),
                    mode='markers+text',
                    text=[self.nodes[theme_id].label for theme_id, _ in themes],
                    textposition="middle right",
                    name=cat.label,
                    showlegend=False
                ),
                row=2, col=2
            )
        
        fig.update_layout(height=800, title_text="知識圖譜統計儀表板")
        return fig
    
    def visualize_query_result(self, age: int, category: str):
        """可視化查詢結果"""
        
        config = self.get_story_config(age, category)
        
        # 創建查詢結果的可視化
        fig = go.Figure()
        
        # 中心節點（查詢參數）
        fig.add_trace(go.Scatter(
            x=[0], y=[0],
            mode='markers+text',
            marker=dict(size=30, color='red'),
            text=f"Query<br>Age:{age}<br>Category:{category}",
            textposition="middle center",
            name="Query Center"
        ))
        
        # 結果節點
        angles = [i * 2 * 3.14159 / 4 for i in range(4)]  # 4個結果維度
        
        result_info = [
                (f"Age Group<br>{config.get('age_group', 'N/A')}", 1),
                (f"Themes<br>{', '.join(list(config.get('themes', []))[:2])}", 2),
                (f"Characters<br>{', '.join(list(config.get('characters', []))[:2])}", 3),
                (f"Complexity<br>{config.get('age_config', {}).get('complexity', 'N/A')}", 4)
        ]
        
        for i, (text, radius) in enumerate(result_info):
            x = radius * np.cos(angles[i])
            y = radius * np.sin(angles[i])
            
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode='markers+text',
                marker=dict(size=20, color=f'hsl({i*90}, 70%, 60%)'),
                text=text,
                textposition="middle center",
                name=f"Result{i+1}",
                showlegend=False
            ))
            
            # 連接線
            fig.add_trace(go.Scatter(
                x=[0, x], y=[0, y],
                mode='lines',
                line=dict(color='gray', width=1),
                showlegend=False,
                hoverinfo='none'
            ))
        
        fig.update_layout(
            title=f"Query Result Visualization - Age {age} {category} Stories",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-3, 3]),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-3, 3]),
            height=600,
            width=800
        )
        
        return fig
    
    def _compute_stats(self) -> Dict:
        """計算統計信息"""
        stats = {
            "node_distribution": {},
            "edge_distribution": {},
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges)
        }
        
        # 節點分佈
        for node in self.nodes.values():
            node_type = node.type.value
            stats["node_distribution"][node_type] = stats["node_distribution"].get(node_type, 0) + 1
        
        # 邊分佈
        for edge in self.edges:
            relation = edge.relation
            stats["edge_distribution"][relation] = stats["edge_distribution"].get(relation, 0) + 1
        
        return stats
    
    def export_to_json(self, filename: str):
        """導出為JSON格式"""
        data = {
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.value,
                    "label": node.label,
                    "properties": node.properties,
                }
                for node in self.nodes.values()
            ],
            "edges": [asdict(edge) for edge in self.edges],
            "metadata": {
                "created_at": pd.Timestamp.now().isoformat(),
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "schema_version": self.KG_SCHEMA_VERSION,
                "ontology": self.get_ontology(),
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    # =============================================================================
    # 9. 圖譜健檢/一致性驗證 (KG Validation)
    # =============================================================================

    def validate(self, strict: bool = False) -> Dict[str, Any]:
        """檢查圖譜是否維持在『可作為知識圖譜』的狀態。

        目標：避免新增資料/類型後，出現「節點孤島」、「邊指向不存在節點」、
        或關係方向/型別不符合語義，導致後續查詢/推論不可靠。

        Args:
            strict: True 則遇到 error 直接 raise ValueError。

        Returns:
            dict: {errors: [...], warnings: [...], summary: {...}}
        """

        errors: List[str] = []
        warnings: List[str] = []

        def _node_type(node_id: str) -> Optional[NodeType]:
            node = self.nodes.get(node_id)
            return None if node is None else node.type

        # 1) 基本一致性：edge 端點存在
        missing_endpoints = 0
        for edge in self.edges:
            if edge.source not in self.nodes:
                missing_endpoints += 1
                errors.append(f"Edge source missing: {edge.source} -> {edge.target} ({edge.relation})")
            if edge.target not in self.nodes:
                missing_endpoints += 1
                errors.append(f"Edge target missing: {edge.source} -> {edge.target} ({edge.relation})")

        # 2) 關係語義：檢查特定 relation 的型別方向
        relation_schema = self.RELATION_SCHEMA

        schema_violations = 0
        for edge in self.edges:
            expected = relation_schema.get(edge.relation)
            if not expected:
                continue
            expected_source, expected_target = expected
            src_type = _node_type(edge.source)
            tgt_type = _node_type(edge.target)

            if expected_source is not None and src_type != expected_source:
                schema_violations += 1
                warnings.append(
                    f"Relation type mismatch: ({edge.relation}) source {edge.source} is {src_type}, expected {expected_source}"
                )

            # suitable_for 的 target 允許 CATEGORY 或 THEME
            if edge.relation == "suitable_for":
                if tgt_type not in {NodeType.CATEGORY, NodeType.THEME}:
                    schema_violations += 1
                    warnings.append(
                        f"Relation type mismatch: (suitable_for) target {edge.target} is {tgt_type}, expected CATEGORY or THEME"
                    )
            elif expected_target is not None and tgt_type != expected_target:
                schema_violations += 1
                warnings.append(
                    f"Relation type mismatch: ({edge.relation}) target {edge.target} is {tgt_type}, expected {expected_target}"
                )

        # 3) 重要節點屬性檢查
        # AGE_GROUP: min_age/max_age/page_range
        for node_id, node in self.nodes.items():
            if node.type == NodeType.AGE_GROUP:
                min_age = node.properties.get("min_age")
                max_age = node.properties.get("max_age")
                page_range = node.properties.get("page_range")
                if not isinstance(min_age, int) or not isinstance(max_age, int) or min_age > max_age:
                    warnings.append(f"AGE_GROUP config invalid: {node_id} min_age/max_age={min_age}/{max_age}")
                if not isinstance(page_range, (list, tuple)) or len(page_range) != 2:
                    warnings.append(f"AGE_GROUP config missing page_range: {node_id} page_range={page_range}")

            if node.type == NodeType.GENERATION_PARAM:
                param_type = node.properties.get("type")
                if param_type not in {"story_structure", "character_dynamic", "story_catalyst"}:
                    warnings.append(f"GENERATION_PARAM has unknown type: {node_id} type={param_type}")
                if not node.properties.get("variation_type"):
                    warnings.append(f"GENERATION_PARAM missing variation_type: {node_id}")
                if not node.properties.get("description"):
                    warnings.append(f"GENERATION_PARAM missing description: {node_id}")

        report = {
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "missing_endpoints": missing_endpoints,
                "schema_violations": schema_violations,
            },
        }

        if strict and errors:
            raise ValueError("KG validation failed: " + " | ".join(errors[:5]))

        return report
    
    def save_visualization(self, fig, filename: str, format='html'):
        """保存可視化結果"""
        if format == 'html':
            fig.write_html(filename)
        elif format == 'png':
            fig.write_image(filename)
        elif format == 'pdf':
            fig.write_image(filename)

# =============================================================================
# 使用示例 (Usage Example)
# =============================================================================

def main_demo():
    """Compatibility entrypoint for the extracted KG demo."""

    from kg_demo import main

    main()


if __name__ == "__main__":
    main_demo()
