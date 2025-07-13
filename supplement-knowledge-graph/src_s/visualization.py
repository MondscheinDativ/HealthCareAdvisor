import networkx as nx
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib_venn import venn2
import os

class KnowledgeGraphVisualizer:
    def __init__(self, graph):
        self.graph = graph
        self.color_map = {
            "supplement": "#4e79a7",
            "disease": "#e15759",
            "ingredient": "#76b7b2",
            "tcm_term": "#f28e2b",
            "default": "#bab0ac"
        }
    
    def _get_node_color(self, node):
        """根据节点类型返回颜色"""
        node_type = self.graph.nodes[node].get("type", "default")
        return self.color_map.get(node_type.split(":")[0], self.color_map["default"])
    
    def plot_network(self, output_prefix="knowledge_graph"):
        """生成网络图可视化"""
        plt.figure(figsize=(20, 15))
        
        # 计算节点大小和颜色
        node_sizes = [self.graph.degree(node) * 50 for node in self.graph.nodes()]
        node_colors = [self._get_node_color(node) for node in self.graph.nodes()]
        
        # 绘制网络
        pos = nx.spring_layout(self.graph, k=0.15, iterations=50)
        nx.draw_networkx_nodes(
            self.graph, pos,
            node_size=node_sizes,
            node_color=node_colors,
            alpha=0.9
        )
        nx.draw_networkx_edges(
            self.graph, pos,
            width=1.0,
            alpha=0.3,
            edge_color="grey"
        )
        
        # 添加标签
        labels = {node: node.split(":")[-1] for node in self.graph.nodes()}
        nx.draw_networkx_labels(
            self.graph, pos,
            labels=labels,
            font_size=8,
            font_family="sans-serif"
        )
        
        # 添加图例
        legend_elements = [
            plt.Line2D([0], [0], marker='o', color='w', label='补剂', 
                      markerfacecolor=self.color_map["supplement"], markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='疾病', 
                      markerfacecolor=self.color_map["disease"], markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='成分', 
                      markerfacecolor=self.color_map["ingredient"], markersize=10),
            plt.Line2D([0], [0], marker='o', color='w', label='中医术语', 
                      markerfacecolor=self.color_map["tcm_term"], markersize=10)
        ]
        plt.legend(handles=legend_elements, loc='best')
        
        plt.title("补剂知识图谱", fontsize=16)
        plt.axis('off')
        
        # 保存多种格式
        plt.savefig(f"images/{output_prefix}.png", dpi=300, bbox_inches='tight')
        plt.savefig(f"images/{output_prefix}.pdf", bbox_inches='tight')
        plt.savefig(f"images/{output_prefix}.svg", format='svg', bbox_inches='tight')
        plt.close()
        print(f"网络图已保存: images/{output_prefix}.[png/pdf/svg]")
    
    def plot_degree_distribution(self):
        """生成度分布直方图"""
        degrees = [d for n, d in self.graph.degree()]
        plt.figure(figsize=(10, 6))
        sns.histplot(degrees, bins=30, kde=True, color="#4e79a7")
        plt.title('节点度分布', fontsize=14)
        plt.xlabel('度', fontsize=12)
        plt.ylabel('频率', fontsize=12)
        plt.grid(axis='y', alpha=0.3)
        plt.savefig("images/degree_distribution.png", dpi=300, bbox_inches='tight')
        plt.savefig("images/degree_distribution.pdf", bbox_inches='tight')
        plt.close()
        print("度分布图已保存: images/degree_distribution.[png/pdf]")
    
    def plot_community_venn(self):
        """生成中西医概念Venn图"""
        # 提取中西医概念
        western_nodes = [n for n, attr in self.graph.nodes(data=True) 
                        if attr.get('type') in ['disease', 'ingredient']]
        tcm_nodes = [n for n, attr in self.graph.nodes(data=True) 
                    if attr.get('type') == 'tcm_term']
        
        # 计算交集
        common_nodes = set(western_nodes) & set(tcm_nodes)
        
        plt.figure(figsize=(8, 8))
        venn2(subsets=(len(western_nodes), len(tcm_nodes), len(common_nodes)),
              set_labels=('西医概念', '中医概念'),
              set_colors=('#4e79a7', '#f28e2b'),
              alpha=0.7)
        plt.title("中西医概念分布", fontsize=14)
        plt.savefig("images/concept_venn.png", dpi=300, bbox_inches='tight')
        plt.savefig("images/concept_venn.pdf", bbox_inches='tight')
        plt.close()
        print("概念Venn图已保存: images/concept_venn.[png/pdf]")
    
    def generate_all_visualizations(self):
        """生成所有可视化图表"""
        # 确保图片目录存在
        os.makedirs("images", exist_ok=True)
        
        self.plot_network()
        self.plot_degree_distribution()
        self.plot_community_venn()
