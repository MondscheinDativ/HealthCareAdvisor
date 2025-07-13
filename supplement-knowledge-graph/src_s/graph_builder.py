import networkx as nx
import pandas as pd

class KnowledgeGraphBuilder:
    def __init__(self, cleaned_data_path):
        self.data = pd.read_csv(cleaned_data_path)
        self.graph = nx.Graph()
        self.ingredient_data = self.load_ingredient_data()
    
    def load_ingredient_data(self):
        """从NIH DSLD加载补剂成分数据"""
        # 简化的静态示例（实际应通过API获取）
        return {
            "复合B族": ["B1", "B2", "B3", "B6", "B12"],
            "锌": ["锌"],
            "镁（甘氨酸镁）": ["镁"],
            "维生素C": ["维生素C"],
            "铁": ["铁"],
            "钙": ["钙"],
            "维生素D": ["维生素D"]
        }
    
    def add_nodes(self):
        """添加节点到知识图谱"""
        # 添加补剂节点
        for _, row in self.data.iterrows():
            supp_name = row['name']
            node_id = f"supplement:{supp_name}"
            self.graph.add_node(node_id, type="supplement", **row.to_dict())
        
        # 添加补剂成分属性
        for supp, ingredients in self.ingredient_data.items():
            node_id = f"supplement:{supp}"
            if node_id in self.graph.nodes:
                self.graph.nodes[node_id]["ingredients"] = ingredients
        
        # 添加疾病节点（示例）
        diseases = ["贫血", "骨质疏松", "免疫力低下", "高血压"]
        for disease in diseases:
            node_id = f"disease:{disease}"
            self.graph.add_node(node_id, type="disease", name=disease)
    
    def add_edges(self):
        """添加关系到知识图谱"""
        # 补剂-成分关系
        for supp, ingredients in self.ingredient_data.items():
            supp_node = f"supplement:{supp}"
            for ingredient in ingredients:
                ing_node = f"ingredient:{ingredient}"
                self.graph.add_node(ing_node, type="ingredient", name=ingredient)
                self.graph.add_edge(supp_node, ing_node, relationship="contains")
        
        # 补剂-疾病关系（示例）
        treatment_mapping = {
            "铁": "贫血",
            "钙": "骨质疏松",
            "维生素C": "免疫力低下",
            "镁（甘氨酸镁）": "高血压"
        }
        
        for supp, disease in treatment_mapping.items():
            supp_node = f"supplement:{supp}"
            disease_node = f"disease:{disease}"
            if supp_node in self.graph.nodes and disease_node in self.graph.nodes:
                self.graph.add_edge(
                    supp_node,
                    disease_node,
                    relationship="treats",
                    evidence_level="A"
                )
    
    def integrate_tcm_knowledge(self):
        """整合中医知识"""
        integrator = TCMIntegrator()
        self.graph = integrator.integrate_tcm_concepts(self.graph)
        return self.graph
    
    def build_and_save(self, output_path="knowledge_graph.gexf"):
        """构建并保存知识图谱"""
        self.add_nodes()
        self.add_edges()
        nx.write_gexf(self.graph, output_path)
        print(f"知识图谱已保存至: {output_path}")
        return self.graph
