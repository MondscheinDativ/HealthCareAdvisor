library(tidyverse)
library(neo4r)
library(future)
library(furrr)
library(digest)
library(disjointSet)

# 并行处理增强性能
plan(multisession, workers = 8)

# 滚动哈希实现字符串归一化
normalize_names <- function(names) {
  sapply(names, function(x) {
    hash <- digest(tolower(x), "xxhash32")
    # 映射到标准名称
    switch(hash,
      "a1b2c3d4" = "维生素C",
      "e5f6g7h8" = "维生素D3",
      x  # 默认返回原名称
    )
  })
}

# 清洗临床实验数据
clean_clinical_trials <- function() {
  files <- list.files("../data/raw/clinical_trials", pattern = "\\.csv$", full.names = TRUE)
  
  combined <- future_map_dfr(files, function(f) {
    suppressMessages(read_csv(f)) %>%
      filter(status %in% c("Completed", "Active, not recruiting")) %>%
      mutate(
        supplement = normalize_names(str_extract(f, "(?<=/)[^/]+(?=\\.csv)")),
        nct_id = as.character(nct_id),
        conditions = map_chr(conditions, ~paste(unique(str_split(.x, ",\\s*")[[1]]), collapse = ", "))
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
    df <- read_csv(f) %>%
      mutate(
        supplement = normalize_names(str_extract(f, "(?<=/)[^/]+(?=\\.csv)")),
        year = str_extract(pub_date, "\\d{4}")
      ) %>%
      distinct(pmid, .keep_all = TRUE)
    
    # 异常值检测
    valid_df <- df %>%
      filter(nchar(title) > 10, nchar(abstract) > 50)
    valid_df
  })
  
  write_csv(combined, "../data/processed/pubmed_clean.csv")
  return(combined)
}

# 并查集实现实体合并
build_entity_union_find <- function(nodes) {
  ds <- disjointSet$new()
  for (node in nodes$id) ds$add(node)
  
  # 添加相似规则
  similar_rules <- list(
    c("维生素C", "维C"),
    c("维生素D3", "VD3")
  )
  
  for (pair in similar_rules) {
    if (all(pair %in% nodes$id)) ds$union(pair[1], pair[2])
  }
  
  # 返回代表元素
  nodes %>%
    mutate(root_id = sapply(id, ds$find)) %>%
    group_by(root_id) %>%
    mutate(canonical_name = first(id))
}

# 构建知识图谱
build_knowledge_graph <- function() {
  # 检查环境变量
  if (Sys.getenv("NEO4J_USER") == "" || Sys.getenv("NEO4J_PASS") == "") {
    message("警告：未检测到Neo4j凭据，将仅生成CSV文件")
    neo4j_enabled <- FALSE
  } else {
    neo4j_enabled <- TRUE
  }
  
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
    ) %>%
    build_entity_union_find()
  
  # 创建关系
  relations <- trials %>%
    select(from = supplement, to = nct_id, rel_type = "STUDIED_IN") %>%
    bind_rows(
      pubmed %>%
        select(from = supplement, to = pmid) %>%
        mutate(rel_type = "RESEARCHED_IN")
    )
  
  # 导出节点和边到CSV
  write_csv(supplement_nodes, "../data/processed/knowledge_graph_nodes.csv")
  write_csv(relations, "../data/processed/knowledge_graph_edges.csv")
  
  # 导出到Neo4j（如果启用）
  if (neo4j_enabled) {
    message("正在连接到Neo4j数据库...")
    con <- neo4j_api$new(
      url = "bolt://localhost:7687",
      user = Sys.getenv("NEO4J_USER"),
      password = Sys.getenv("NEO4J_PASS")
    )
    
    # 检查连接
    test_query <- "RETURN 'Connection successful' AS result"
    test_result <- tryCatch(
      call_neo4j(test_query, con),
      error = function(e) {
        message("Neo4j连接失败: ", e$message)
        return(NULL)
      }
    )
    
    if (!is.null(test_result)) {
      message("成功连接到Neo4j，开始导入数据...")
      
      # 批量导入节点
      import_nodes(supplement_nodes, con, "Supplement")
      
      # 批量导入关系
      import_relations(relations, con)
      
      message("Neo4j数据导入完成")
    } else {
      message("跳过Neo4j数据导入")
    }
  }
}

# 辅助函数：批量导入节点
import_nodes <- function(nodes, con, label) {
  batch_size <- 500
  batches <- split(nodes, (seq(nrow(nodes)) %/% batch_size))
  
  for(batch in batches) {
    query <- paste0(
      "UNWIND $nodes AS node ",
      "MERGE (s:", label, " {id: node.id}) ",
      "SET s += apoc.map.removeKeys(node, ['id'])"
    )
    tryCatch({
      call_neo4j(query, con, parameters = list(nodes = as.list(batch)))
      message("导入节点批次: ", length(batch), " 条记录")
    }, error = function(e) {
      message("节点导入失败: ", e$message)
    })
  }
}

# 辅助函数：批量导入关系
import_relations <- function(relations, con) {
  batch_size <- 500
  batches <- split(relations, (seq(nrow(relations)) %/% batch_size))
  
  for(batch in batches) {
    query <- "
    UNWIND $rels AS rel
    MATCH (from {id: rel.from})
    MATCH (to {id: rel.to})
    MERGE (from)-[r:`RELATED_TO`]->(to)
    SET r.type = rel.rel_type
    "
    tryCatch({
      call_neo4j(query, con, parameters = list(rels = as.list(batch)))
      message("导入关系批次: ", length(batch), " 条记录")
    }, error = function(e) {
      message("关系导入失败: ", e$message)
    })
  }
}
