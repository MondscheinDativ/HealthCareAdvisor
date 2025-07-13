library(tidyverse)
library(neo4r)
library(future)
library(furrr)

# 并行处理增强性能
plan(multisession, workers = 8)

# 清洗临床实验数据
clean_clinical_trials <- function() {
  files <- list.files("../data/raw/clinical_trials", pattern = "\\.csv$", full.names = TRUE)
  
  combined <- future_map_dfr(files, function(f) {
    suppressMessages(read_csv(f)) %>%
      filter(status %in% c("Completed", "Active, not recruiting")) %>%
      mutate(
        supplement = str_extract(f, "(?<=/)[^/]+(?=\\.csv)"),
        nct_id = as.character(nct_id),
        conditions = map_chr(conditions, ~paste(unique(str_split(.x, ",\\s*")[[1]], collapse = ", "))
      ) %>%
      distinct(nct_id, .keep_all = TRUE)
  })
  
  write_csv(combined, "../data/processed/clinical_trials_clean.csv")
  return(combined)
}

# 清洗PubMed数据
clean_pubmed_data <- function() {
  files <- list.files("../data/raw/pubmed", pattern = "\\.csv$", full.names = TRUE)
  
  combined <- future_map_dfr(files, function(f) {
    suppressMessages(read_csv(f)) %>%
      mutate(
        supplement = str_extract(f, "(?<=/)[^/]+(?=\\.csv)"),
        year = str_extract(pub_date, "\\d{4}")
      ) %>%
      distinct(pmid, .keep_all = TRUE)
  })
  
  write_csv(combined, "../data/processed/pubmed_clean.csv")
  return(combined)
}

# 构建知识图谱
build_knowledge_graph <- function() {
  trials <- read_csv("../data/processed/clinical_trials_clean.csv")
  pubmed <- read_csv("../data/processed/pubmed_clean.csv")
  
  # 创建节点
  supplement_nodes <- trials %>%
    distinct(supplement) %>%
    bind_rows(pubmed %>% distinct(supplement)) %>%
    distinct() %>%
    mutate(
      type = "Supplement", 
      id = supplement,
      label = supplement
    )
  
  # 创建关系
  relations <- trials %>%
    select(from = supplement, to = nct_id, rel_type = "STUDIED_IN") %>%
    bind_rows(
      pubmed %>%
        select(from = supplement, to = pmid) %>%
        mutate(rel_type = "RESEARCHED_IN")
    )
  
  # 导出到Neo4j
  con <- neo4j_api$new(
    url = "bolt://localhost:7687", 
    user = Sys.getenv("NEO4J_USER"), 
    password = Sys.getenv("NEO4J_PASS")
  )
  
  # 批量导入节点
  import_nodes(supplement_nodes, con, "Supplement")
  
  # 批量导入关系
  import_relations(relations, con)
}

# 辅助函数：批量导入节点
import_nodes <- function(nodes, con, label) {
  batch_size <- 500
  batches <- split(nodes, (seq(nrow(nodes)) %/% batch_size)
  
  for(batch in batches) {
    query <- paste0(
      "UNWIND $nodes AS node ",
      "MERGE (s:", label, " {id: node.id}) ",
      "SET s += apoc.map.removeKeys(node, ['id'])"
    )
    call_neo4j(query, con, parameters = list(nodes = as.list(batch)))
  }
}

# 辅助函数：批量导入关系
import_relations <- function(relations, con) {
  batch_size <- 500
  batches <- split(relations, (seq(nrow(relations)) %/% batch_size)
  
  for(batch in batches) {
    query <- "
      UNWIND $rels AS rel
      MATCH (from {id: rel.from})
      MATCH (to {id: rel.to})
      MERGE (from)-[r:`RELATED_TO`]->(to)
      SET r.type = rel.rel_type
    "
    call_neo4j(query, con, parameters = list(rels = as.list(batch)))
  }
}
