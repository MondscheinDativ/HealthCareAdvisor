library(visNetwork)
library(neo4r)
library(dplyr)

visualize_core_graph <- function(focus_supplement = "维生素D3", depth = 2) {
  con <- neo4j_api$new(
    url = "bolt://localhost:7687", 
    user = Sys.getenv("NEO4J_USER"), 
    password = Sys.getenv("NEO4J_PASS")
  )
  
  query <- paste0("
    MATCH path = (s:Supplement {id: '", focus_supplement, "'})-[*..", depth, "]-(related)
    WITH nodes(path) AS nodes, relationships(path) AS rels
    UNWIND nodes AS node
    UNWIND rels AS rel
    RETURN 
      COLLECT(DISTINCT node) AS nodes, 
      COLLECT(DISTINCT {
        source: startNode(rel).id, 
        target: endNode(rel).id,
        type: type(rel)
      }) AS relationships
  ")
  
  result <- call_neo4j(query, con, type = "graph")
  
  if(length(result$nodes) == 0) {
    message("No results found for: ", focus_supplement)
    return(NULL)
  }
  
  # 准备节点数据
  nodes_df <- bind_rows(result$nodes) %>%
    mutate(
      label = coalesce(properties$label, properties$id),
      group = ifelse(id == focus_supplement, "Focus", label),
      value = ifelse(group == "Focus", 30, 10),
      title = paste0("<b>", label, "</b><br>Type: ", label)
    ) %>%
    distinct(id, .keep_all = TRUE)
  
  # 准备关系数据
  edges_df <- bind_rows(result$relationships) %>%
    mutate(
      title = type,
      dashes = ifelse(type == "RESEARCHED_IN", TRUE, FALSE)
    )
  
  # 创建可视化
  visNetwork(nodes_df, edges_df) %>%
    visNodes(shape = "dot") %>%
    visEdges(arrows = "to") %>%
    visOptions(
      highlightNearest = list(enabled = TRUE, degree = 2),
      nodesIdSelection = TRUE
    ) %>%
    visLayout(randomSeed = 123) %>%
    visPhysics(
      stabilization = list(iterations = 100),
      repulsion = list(nodeDistance = 300)
    ) %>%
    visSave(file = paste0(focus_supplement, "_knowledge_graph.html"))
  
  return(nodes_df)
}
