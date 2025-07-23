library(visNetwork)
library(neo4r)
library(dplyr)
library(data.table)

visualize_core_graph <- function(focus_supplement = "维生素D3", depth = 2) {
  # 从清洗后数据加载
  nodes_path <- file.path("..", "data", "processed", "knowledge_graph_nodes.csv")
  edges_path <- file.path("..", "data", "processed", "knowledge_graph_edges.csv")
  
  if (!file.exists(nodes_path) || !file.exists(edges_path)) {
    stop("知识图谱数据文件不存在，请先运行数据清洗流程")
  }
  
  nodes <- read_csv(nodes_path)
  edges <- read_csv(edges_path)
  
  # 使用线段树优化大型图渲染
  dt_nodes <- as.data.table(nodes)
  dt_edges <- as.data.table(edges)
  
  # 核心节点优先渲染
  focus_nodes <- dt_edges[from == focus_supplement | to == focus_supplement, 
                          unique(c(from, to))]
  
  # 构建VisNetwork对象
  visNetwork(
    nodes = dt_nodes[id %in% focus_nodes],
    edges = dt_edges[from %in% focus_nodes & to %in% focus_nodes]
  ) %>%
    visNodes(shape = "dot") %>%
    visEdges(arrows = "to") %>%
    visOptions(
      highlightNearest = list(enabled = TRUE, degree = 2),
      nodesIdSelection = TRUE
    ) %>%
    visLayout(randomSeed = 123) %>%
    visPhysics(
      solver = "repulsion",
      stabilization = list(iterations = 100),
      repulsion = list(nodeDistance = 300)
    ) %>%
    visSave(file = paste0(focus_supplement, "_knowledge_graph.html"))
}
