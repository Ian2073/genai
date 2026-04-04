"""Knowledge graph demo entrypoint separated from core kg module."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kg import StoryGenerationKG


def main() -> None:
    """主要演示功能。"""

    kg = StoryGenerationKG()

    print("=== Enhanced Story Generation Knowledge Graph Demo ===\n")

    print("0. KG Integrity Validation:")
    validation = kg.validate(strict=False)
    summary = validation.get("summary", {})
    print(
        f"  Nodes: {summary.get('total_nodes')} | Edges: {summary.get('total_edges')} | "
        f"Missing endpoints: {summary.get('missing_endpoints')} | Schema warnings: {summary.get('schema_violations')}"
    )
    if validation.get("errors"):
        print(f"  Errors: {len(validation['errors'])}")
        for msg in validation["errors"][:5]:
            print(f"    - {msg}")
    if validation.get("warnings"):
        print(f"  Warnings: {len(validation['warnings'])}")
        for msg in validation["warnings"][:5]:
            print(f"    - {msg}")
    print()

    print("1. Query 6-year-old Educational Story Configuration:")
    config = kg.get_story_config(age=6, category="educational")
    print(f"  Age Group: {config.get('age_group')}")
    print(f"  Category: {config.get('category')}")
    print(f"  Themes: {list(config.get('themes', {}).keys())[:5]}")
    print(f"  Characters: {list(config.get('characters', {}).keys())}")
    print()

    print("2. Random Story Configuration:")
    random_config = kg.get_random_story_config(age=7)
    print(f"Selected Category: {random_config.get('category')}")
    print(f"Selected Structure: {random_config.get('selected_structure', {}).get('label')}")
    print(f"Selected Dynamic: {random_config.get('selected_dynamic', {}).get('label')}")
    print(f"Selected Catalyst: {random_config.get('selected_catalyst', {}).get('label')}")
    if "selected_subcategory" in random_config:
        print(f"Selected Subcategory: {random_config['selected_subcategory']}")
    print()

    print("3. Create Story Generation Session:")
    session_id = kg.create_generation_session("enhanced_demo_001", config)
    print(f"Session ID: {session_id}")

    kg.update_generation_state(
        "enhanced_demo_001",
        {
            "status": "generating",
            "pages_generated": 5,
            "current_themes": ["friendship", "sharing"],
            "selected_variations": {
                "structure": random_config.get("selected_structure", {}).get("type"),
                "catalyst": random_config.get("selected_catalyst", {}).get("type"),
            },
        },
    )
    print("Updated generation state with variation tracking")
    print()

    print("4. Category-Specific Configuration Examples:")
    categories = ["educational", "adventure", "fun", "cultural"]
    for category in categories:
        cat_config = kg.get_story_config(age=6, category=category, include_variations=False)
        print(f"\n{category.upper()} Category:")
        if "category_config" in cat_config and "subcategories" in cat_config["category_config"]:
            subcats = list(cat_config["category_config"]["subcategories"].keys())
            print(f"  Subcategories: {subcats}")
            if subcats:
                first_subcat = cat_config["category_config"]["subcategories"][subcats[0]]
                if "themes" in first_subcat:
                    print(f"  Sample Themes: {first_subcat['themes'][:3]}")

    print("\n" + "=" * 50)
    print("ACADEMIC ENHANCEMENTS DEMO")
    print("=" * 50)

    print("\n6. Relation-Centric Query (First-class relation objects):")
    suitable_edges = kg.get_edges_by_relation("suitable_for")
    print(f"Found {len(suitable_edges)} 'suitable_for' relations.")
    print("Example: Age groups suitable for 'Adventure':")
    sources = kg.get_sources_by_relation("adventure", "suitable_for")
    for source in sources:
        print(f"  - {source.label}")

    print("\n[New] Verifying Variation Relations:")
    print("Example: Structures suitable for 'Adventure':")
    structures = kg.get_sources_by_relation("adventure", "structure_suitable_for")
    for source in structures:
        print(f"  - {source.label}")

    print("\n7. Graph Inference Engine:")
    print("Running inference rules...")
    new_edges_count = kg.infer_relations()
    print(f"Inferred {new_edges_count} new relations based on graph structure.")

    print("Verifying inference (Transitivity: Age -> Theme):")
    inferred_edges = [edge for edge in kg.edges if edge.properties.get("inferred")]
    if inferred_edges:
        example = inferred_edges[0]
        source_node = kg.nodes[example.source]
        target_node = kg.nodes[example.target]
        print(f"  Inferred: {source_node.label} -> {target_node.label} ({example.relation})")
        print(f"  Rule: {example.properties.get('rule')}")

    print("\n8. Pure Knowledge Subgraph (Decoupled from Generation):")
    subgraph = kg.get_subgraph("educational", depth=1)
    print("Subgraph centered on 'Educational':")
    print(f"  Nodes: {len(subgraph['nodes'])}")
    print(f"  Edges: {len(subgraph['edges'])}")
    print("  This proves knowledge exists independently of the story pipeline.")

    print("\n" + "=" * 50)
    print("9. Generating Visualization Charts...")

    full_graph = kg.visualize_full_graph()
    kg.save_visualization(full_graph, "enhanced_knowledge_graph.html")
    print("[OK] Enhanced knowledge graph saved as enhanced_knowledge_graph.html")

    stats_fig = kg.visualize_generation_stats()
    kg.save_visualization(stats_fig, "enhanced_kg_stats.html")
    print("[OK] Enhanced statistics dashboard saved as enhanced_kg_stats.html")

    query_fig = kg.visualize_query_result(6, "educational")
    kg.save_visualization(query_fig, "enhanced_query_result.html")
    print("[OK] Enhanced query result saved as enhanced_query_result.html")

    kg.export_to_json("enhanced_knowledge_graph_data.json")
    print("[OK] Enhanced knowledge graph data exported as enhanced_knowledge_graph_data.json")

    print("\n=== Enhanced Demo Complete ===")
    print("The system now includes:")
    print("  [+] Complete story category configurations")
    print("  [+] Layered variation systems")
    print("  [+] Universal story elements")
    print("  [+] Random configuration generation")
    print("  [+] Enhanced query capabilities")
    print("  [+] Relation-centric query API (Academic Requirement 1)")
    print("  [+] Graph inference engine (Academic Requirement 2)")
    print("  [+] Decoupled knowledge access (Academic Requirement 3)")
    print("\nOpen the generated HTML files to view enhanced visualizations!")


if __name__ == "__main__":
    required_packages = ["networkx", "plotly", "pandas", "numpy"]
    print("請確保已安裝以下包：")
    for pkg in required_packages:
        print(f"  pip install {pkg}")
    print()
    main()
