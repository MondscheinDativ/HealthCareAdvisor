import requests

class TCMIntegrator:
    def __init__(self):
        self.mapping_table = self.load_mapping_table()
    
    def load_mapping_table(self):
        """加载中西医术语映射表"""
        return {
            "气血不足": "贫血",
            "肝火旺盛": "高血压",
            "肾虚": "骨质疏松",
            "卫气不固": "免疫力低下",
            "脾胃虚弱": "消化不良"
        }
    
    def integrate_tcm_concepts(self, graph):
        """将中医概念整合到知识图谱"""
        # 添加中医术语节点
        for term, western_term in self.mapping_table.items():
            node_id = f"tcm:{term}"
            graph.add_node(node_id, type="tcm_term", name=term, 
                          western_equivalent=western_term)
            
            # 关联相应西医概念
            disease_node = f"disease:{western_term}"
            if disease_node in graph.nodes:
                graph.add_edge(
                    node_id,
                    disease_node,
                    relationship="equivalent_to",
                    source="TCMKB"
                )
        
        return graph
