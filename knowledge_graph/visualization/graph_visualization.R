library(visNetwork)
library(igraph)

visualize_core_graph <- function(supplement_focus = "NMN") {
  # 从Neo4j获取核心关系
  query <- paste0("
    MATCH (s:Supplement {id: '", supplement_focus, "'})-[r]-(related)
    RETURN s, r, related
    LIMIT 50
  ")
  
  graph_data <- call_neo4j(query, con, type = "graph")
  
  # 转换为visNetwork格式
  nodes <- graph_data$nodes %>%
    mutate(
      label = coalesce(properties$name, properties$id),
      group = ifelse(label == supplement_focus, "Focus", label_type)
    )
  
  edges <- graph_data$relationships %>%
    mutate(
      from = startNode,
      to = endNode,
      label = type
    )
  
  # 生成可视化
  visNetwork(nodes, edges) %>%
    visGroups(groupname = "Focus", color = "#FF0000") %>%
    visLegend() %>%
    visPhysics(stabilization = FALSE) %>%
    visSave(file = "core_knowledge_graph.html")
}
