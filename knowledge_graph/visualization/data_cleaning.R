library(tidyverse)
library(neo4r)
library(future)
library(furrr)
library(digest)
library(igraph)  # 新增：用于替代disjointSet实现实体合并

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

# 替代disjointSet：用igraph实现实体合并（并查集功能）
build_entity_union_find <- function(nodes) {
  # 1. 初始化图（节点为实体id）
  g <- make_empty_graph(n = nrow(nodes), directed = FALSE)
  V(g)$name <- nodes$id  # 用实体id作为图节点名称
  
  # 2. 定义相似实体规则（原disjointSet的union逻辑）
  similar_rules <- list(
    c("维生素C", "维C"),
    c("维生素D3", "VD3")
  )
  
  # 3. 为相似实体添加边（表示“需要合并”）
  for (pair in similar_rules) {
    # 仅当两个实体都存在于节点中时才添加边
    if (all(pair %in% nodes$id)) {
      g <- add_edges(g, pair)
    }
  }
  
  # 4. 计算连通分量（等价于并查集的“根节点”）
  components <- components(g)
  # 为每个节点分配对应的根节点id（连通分量的代表）
  nodes <- nodes %>%
    mutate(
      root_id = components$membership[match(id, names(components$membership))],
      root_id = as.character(root_id)  # 转为字符串，避免数值型冲突
    )
  
  # 5. 确定每个连通分量的规范名称（取第一个实体id）
  nodes <- nodes %>%
    group_by(root_id) %>%
    mutate(canonical_name = first(id)) %>%
    ungroup()
  
  return(nodes)
}

# 构建知识图谱（修复supplement列缺失问题）
build_knowledge_graph <- function() {
  # 1. 强制设置：在GitHub Actions中完全禁用Neo4j
  is_ci <- Sys.getenv("GITHUB_ACTIONS") == "true"
  if (is_ci) {
    message("===== 检测到GitHub Actions环境，强制禁用Neo4j连接 =====")
    neo4j_enabled <- FALSE
  } else {
    # 本地环境才检查凭据
    if (Sys.getenv("NEO4J_USER") == "" || Sys.getenv("NEO4J_PASS") == "") {
      message("警告：未检测到Neo4j凭据，将仅生成CSV文件")
      neo4j_enabled <- FALSE
    } else {
      neo4j_enabled <- TRUE
    }
  }
  
  # 2. 读取清洗后的数据
  trials <- tryCatch({
    read_csv("../data/processed/clinical_trials_clean.csv")
  }, error = function(e) {
    message("未找到临床实验数据，使用空表...")
    tibble()
  })
  
  pubmed <- tryCatch({
    read_csv("../data/processed/pubmed_clean.csv")
  }, error = function(e) {
    stop("错误：未找到PubMed数据，请先运行数据清洗流程")
  })
  
  # 3. 创建节点
  if (nrow(trials) > 0 && nrow(pubmed) > 0) {
    supplement_nodes <- trials %>%
      distinct(supplement) %>%
      bind_rows(pubmed %>% distinct(supplement)) %>%
      distinct()
  } else if (nrow(trials) > 0) {
    supplement_nodes <- trials %>% distinct(supplement)
  } else if (nrow(pubmed) > 0) {
    supplement_nodes <- pubmed %>% distinct(supplement)
  } else {
    stop("错误：trials和pubmed数据均为空，无法构建知识图谱")
  }
  
  # 处理节点
  supplement_nodes <- supplement_nodes %>%
    mutate(
      type = "Supplement",
      id = supplement,
      label = supplement
    ) %>%
    build_entity_union_find()
  
  # 4. 创建关系
  relations <- tibble()
  if (nrow(trials) > 0) {
    trials_relations <- trials %>%
      select(from = supplement, to = nct_id, rel_type = "STUDIED_IN")
    relations <- bind_rows(relations, trials_relations)
  }
  
  pubmed_relations <- pubmed %>%
    select(from = supplement, to = pmid) %>%
    mutate(rel_type = "RESEARCHED_IN")
  relations <- bind_rows(relations, pubmed_relations)
  
  # 5. 导出CSV（核心数据，必须执行）
  write_csv(supplement_nodes, "../data/processed/knowledge_graph_nodes.csv")
  write_csv(relations, "../data/processed/knowledge_graph_edges.csv")
  message("知识图谱CSV数据已成功生成")
  
  # 6. 仅在本地环境且启用时连接Neo4j
  if (neo4j_enabled && !is_ci) {
    message("正在连接到本地Neo4j数据库...")
    con <- tryCatch({
      neo4j_api$new(
        url = "http://localhost:7474",
        user = Sys.getenv("NEO4J_USER"),
        password = Sys.getenv("NEO4J_PASS")
      )
    }, error = function(e) {
      message("Neo4j初始化失败: ", e$message)
      return(NULL)
    })
    
    if (!is.null(con)) {
      test_query <- "RETURN 'Connection successful' AS result"
      test_result <- tryCatch(
        call_neo4j(test_query, con),
        error = function(e) {
          message("Neo4j连接测试失败: ", e$message)
          return(NULL)
        }
      )
      
      if (!is.null(test_result)) {
        message("成功连接到Neo4j，开始导入数据...")
        import_nodes(supplement_nodes, con, "Supplement")
        import_relations(relations, con)
        message("Neo4j数据导入完成")
      } else {
        message("跳过Neo4j数据导入")
      }
    }
  } else {
    if (is_ci) {
      message("===== GitHub Actions环境：已跳过Neo4j相关操作 =====")
    } else {
      message("未启用Neo4j，仅保留CSV数据")
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
      message("导入节点批次: ", nrow(batch), " 条记录")
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
      message("导入关系批次: ", nrow(batch), " 条记录")
    }, error = function(e) {
      message("关系导入失败: ", e$message)
    })
  }
}
