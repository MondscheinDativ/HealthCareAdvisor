library(tidyverse)
library(ggraph)
library(igraph)
library(ggtext)
library(knitr)
library(rmarkdown)
library(visNetwork)  # 补充交互式可视化依赖

# 1. 加载已爬取的数据（增加容错）
load_data <- function(supplement = "维生素D3") {
  trials_path <- file.path("..", "data", "processed", "clinical_trials_clean.csv")
  pubmed_path <- file.path("..", "data", "processed", "pubmed_clean.csv")
  
  # 处理临床试验数据可能不存在的情况
  if (!file.exists(trials_path)) {
    message("警告：未找到临床试验数据，将使用空表")
    trials <- tibble()
  } else {
    trials <- read_csv(trials_path) %>% filter(supplement == !!supplement)
  }
  
  # 确保PubMed数据存在
  if (!file.exists(pubmed_path)) {
    stop("错误：PubMed数据文件不存在，请先运行数据清洗流程")
  }
  pubmed <- read_csv(pubmed_path) %>% filter(supplement == !!supplement)
  
  list(trials = trials, pubmed = pubmed)
}

# 2. 专业统计分析（修正top_n为slice_max）
perform_statistical_analysis <- function(data) {
  # 临床试验阶段分布
  phase_dist <- data$trials %>%
    count(phase = `Phase`) %>%
    drop_na()
  
  # 文献发表年份趋势
  pub_year_trend <- data$pubmed %>%
    mutate(year = str_extract(pub_date, "\\d{4}") %>% as.integer()) %>%
    filter(year >= 2010) %>%
    count(year) %>%
    complete(year = 2010:year(Sys.Date()), fill = list(n = 0))
  
  # 疾病关联强度（修正top_n）
  condition_association <- data$trials %>%
    separate_rows(conditions, sep = ", ") %>%
    count(conditions, sort = TRUE) %>%
    slice_max(n, n = 10) %>%  # 替代top_n，更稳定
    mutate(association_strength = n / max(n))
  
  list(
    phase_dist = phase_dist,
    pub_year_trend = pub_year_trend,
    condition_association = condition_association
  )
}

# 3. 专业级知识图谱可视化（保持不变）
create_professional_graph <- function(data, stats, supplement) {
  nodes <- tibble(
    name = c(supplement,
             "临床试验",
             "研究文献",
             stats$condition_association$conditions,
             unique(stats$phase_dist$phase))
  ) %>%
    mutate(
      id = row_number(),
      type = case_when(
        name == supplement ~ "core",
        name %in% c("临床试验", "研究文献") ~ "category",
        name %in% stats$condition_association$conditions ~ "condition",
        TRUE ~ "phase"
      ),
      size = case_when(
        type == "core" ~ 15,
        type == "category" ~ 10,
        type == "condition" ~ 
          stats$condition_association$association_strength[match(name, stats$condition_association$conditions)] * 8 + 3,
        TRUE ~ 5
      )
    )
  
  edges <- tibble(
    from = c(1, 1, 2, 2, 3, 3),
    to = c(2, 3, 4:(3+nrow(stats$condition_association)), 
      (4+nrow(stats$condition_association)):nrow(nodes)),
    relation = c("has_trials", "has_studies", "treats", "treats", "published_in", "published_in")
  )
  
  graph <- graph_from_data_frame(edges, vertices = nodes)
  
  ggraph(graph, layout = "fr") +
    geom_edge_link(aes(color = relation),
                  arrow = arrow(length = unit(2, 'mm')),
                  end_cap = circle(3, 'mm'),
                  alpha = 0.7) +
    geom_node_point(aes(size = size, color = type), alpha = 0.9) +
    geom_node_text(aes(label = name), repel = TRUE, size = 3.5, 
                   bg.color = "white", bg.r = 0.1) +
    scale_size_continuous(range = c(3, 15)) +
    scale_color_manual(values = c(
      "core" = "#E41A1C",
      "category" = "#377EB8",
      "condition" = "#4DAF4A",
      "phase" = "#984EA3"
    )) +
    labs(title = paste0(supplement, "知识图谱 - 生物统计分析"),
         subtitle = "展示临床试验、研究文献与疾病关联",
         caption = paste("数据来源: ClinicalTrials.gov & PubMed |", Sys.Date())) +
    theme_void() +
    theme(
      plot.title = element_text(size = 18, face = "bold", hjust = 0.5),
      plot.subtitle = element_text(size = 14, hjust = 0.5),
      plot.caption = element_text(size = 10, color = "gray50"),
      legend.position = "bottom"
    )
}

# 4. 生成PDF报告（修正输出路径）
generate_professional_report <- function(supplement = "维生素D3") {
  data <- load_data(supplement)
  stats <- perform_statistical_analysis(data)
  
  rmd_content <- paste0(
    "---",
    "title: '", supplement, "知识图谱专业分析报告'",
    "author: '生物统计知识图谱项目'",
    "date: '", Sys.Date(), "'",
    "output: pdf_document",
    "---",
    "\n\n",
    "## 执行摘要\n",
    "本报告展示了", supplement, "的临床试验与研究文献的统计分析结果，",
    "包含知识图谱可视化、疾病关联强度及研究趋势分析。\n\n",
    "## 数据概览\n",
    "- **临床试验数量**: ", nrow(data$trials), "\n",
    "- **研究文献数量**: ", nrow(data$pubmed), "\n",
    "- **分析时间范围**: 2010-", format(Sys.Date(), "%Y"), "\n\n",
    "## 知识图谱可视化\n",
    "```{r graph, echo=FALSE, fig.cap='", supplement, "知识图谱', fig.align='center', fig.height=8}",
    "create_professional_graph(data, stats, '", supplement, "')",
    "```\n\n",
    "## 关键统计分析\n",
    "### 临床试验阶段分布\n",
    "```{r phase, echo=FALSE}",
    "knitr::kable(stats$phase_dist, col.names = c('阶段', '数量'), format = 'pipe')",
    "```\n\n",
    "### 文献发表趋势\n",
    "```{r trend, echo=FALSE, fig.cap='文献发表年度趋势', fig.height=4}",
    "ggplot(stats$pub_year_trend, aes(x = year, y = n)) +",
    "  geom_line(color = '#377EB8', size = 1.2) +",
    "  geom_point(color = '#E41A1C', size = 3) +",
    "  labs(x = '年份', y = '文献数量') +",
    "  theme_minimal() +",
    "  theme(panel.grid.minor = element_blank())",
    "```\n\n",
    "### 疾病关联强度Top10\n",
    "```{r conditions, echo=FALSE}",
    "stats$condition_association %>%",
    "  select(疾病 = conditions, 关联强度 = association_strength, 研究数量 = n) %>%",
    "  knitr::kable(format = 'pipe', digits = 2)",
    "```"
  )
  
  writeLines(rmd_content, "professional_report.Rmd")
  
  # 修正输出路径，确保文件生成在当前目录
  output_file <- paste0(supplement, "_knowledge_graph.pdf")
  render("professional_report.Rmd", output_file = output_file)
  
  file.remove("professional_report.Rmd")
  
  message("专业报告已生成: ", output_file)
}

# 执行生成报告（仅在手动运行时触发，避免GitHub Actions中重复执行）
if (interactive()) {
  generate_professional_report()
}
