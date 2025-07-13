library(tidyverse)
library(neo4r)

# 清洗临床实验数据
clean_clinical_trials <- function() {
  files <- list.files("../data/raw/clinical_trials", full.names = TRUE)
  
  combined <- map_df(files, function(f) {
    read_csv(f) %>%
      filter(status == "Completed") %>%
      mutate(
        supplement = str_extract(f, "(?<=/)[^/]+(?=\\.csv)"),
        nct_id = as.character(nct_id)
      )
  })
  
  # 保存清洗后数据
  write_csv(combined, "../data/processed/clinical_trials_clean.csv")
}

# 构建知识图谱节点关系
build_kg_relations <- function() {
  trials <- read_csv("../data/processed/clinical_trials_clean.csv")
  
  # 创建三种节点类型
  supplement_nodes <- trials %>%
    distinct(supplement) %>%
    mutate(type = "Supplement", id = supplement)
  
  condition_nodes <- trials %>%
    distinct(conditions) %>%
    separate_rows(conditions, sep = ", ") %>%
    distinct(conditions) %>%
    mutate(type = "Condition", id = conditions)
  
  trial_nodes <- trials %>%
    distinct(nct_id, title) %>%
    mutate(type = "Trial", id = nct_id)
  
  # 创建关系
  relations <- trials %>%
    select(supplement, nct_id, conditions) %>%
    separate_rows(conditions, sep = ", ") %>%
    mutate(
      from = supplement,
      to = conditions,
      rel_type = "TREATS"
    ) %>%
    bind_rows(
      trials %>%
        select(from = supplement, to = nct_id) %>%
        mutate(rel_type = "STUDIED_IN")
    )
  
  # 导出为Neo4j兼容格式
  con <- neo4j_api$new(url = "bolt://localhost:7687", user = "neo4j", password = "password")
  
  # 推送节点 (实际使用应分批处理)
  supplement_nodes %>% as_neo4j_nodes("Supplement") %>% call_neo4j(con)
  condition_nodes %>% as_neo4j_nodes("Condition") %>% call_neo4j(con)
  trial_nodes %>% as_neo4j_nodes("Trial") %>% call_neo4j(con)
  
  # 推送关系
  relations %>% as_neo4j_relationships() %>% call_neo4j(con)
}
