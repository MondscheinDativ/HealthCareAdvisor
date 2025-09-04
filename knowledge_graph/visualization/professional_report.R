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
  
  if (!file.exists(trials_path)) {
    message("警告：未找到临床试验数据，将使用空表")
    trials <- tibble()
  } else {
    trials <- read_csv(trials_path) %>% filter(supplement == !!supplement)
  }
  
  if (!file.exists(pubmed_path)) {
    stop("错误：PubMed数据文件不存在，请先运行数据清洗流程")
  }
  pubmed <- read_csv(pubmed_path) %>% filter(supplement == !!supplement)
  
  list(trials = trials, pubmed = pubmed)
}

# 2. 专业统计分析
perform_statistical_analysis <- function(data) {
  phase_dist <- if (nrow(data$trials) > 0) {
    data$trials %>% count(phase = `Phase`) %>% drop_na()
  } else {
    tibble(phase = character(), n = integer())
  }
  
  pub_year_trend <- data$pubmed %>%
    mutate(year = str_extract(pub_date, "\\d{4}") %>% as.integer()) %>%
    filter(year >= 2010) %>%
    count(year) %>%
    complete(year = 2010:year(Sys.Date()), fill = list(n = 0))
  
  condition_association <- if (nrow(data$trials) > 0) {
    data$trials %>%
      separate_rows(conditions, sep = ", ") %>%
      count(conditions, sort = TRUE) %>%
      slice_max(n, n = 10) %>%
      mutate(association_strength = n / max(n))
  } else {
    tibble(conditions = character(), n = integer(), association_strength = numeric())
  }
  
  list(
    phase_dist = phase_dist,
    pub_year_trend = pub_year_trend,
    condition_association = condition_association
  )
}

# 3. 知识图谱可视化
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

# 4. 生成报告（支持 PDF + HTML，自定义输出文件名）
generate_professional_report <- function(supplement = "维生素D3",
                                         output_pdf = NULL,
                                         output_html = NULL) {
  data <- load_data(supplement)
  stats <- perform_statistical_analysis(data)
  
  rmd_content <- paste0(
    "---\n",
    "title: '", supplement, "知识图谱专业分析报告'\n",
    "author: '生物统计知识图谱项目'\n",
    "date: '", Sys.Date(), "'\n",
    "output:\n",
    "  pdf_document: default\n",
    "  html_document: default\n",
    "---\n\n",
    "## 执行摘要\n",
    "本报告展示了", supplement, "的临床试验与研究文献的统计分析结果，",
    "包含知识图谱可视化、疾病关联强度及研究趋势分析。\n\n",
    "## 数据概览\n",
    "- **临床试验数量**: ", nrow(data$trials), "\n",
    "- **研究文献数量**: ", nrow(data$pubmed), "\n",
    "- **分析时间范围**: 2010-", format(Sys.Date(), "%Y"), "\n\n",
    "## 知识图谱可视化\n",
    "```{r graph, echo=FALSE, fig.cap='", supplement, "知识图谱', fig.align='center', fig.height=8}\n",
    "create_professional_graph(data, stats, '", supplement, "')\n",
    "```\n\n",
    "## 关键统计分析\n",
    "### 临床试验阶段分布\n",
    "```{r phase, echo=FALSE}\n",
    "knitr::kable(stats$phase_dist, col.names = c('阶段', '数量'), format = 'pipe')\n",
    "```\n\n",
    "### 文献发表趋势\n",
    "```{r trend, echo=FALSE, fig.cap='文献发表年度趋势', fig.height=4}\n",
    "ggplot(stats$pub_year_trend, aes(x = year, y = n)) +\n",
    "  geom_line(color = '#377EB8', size = 1.2) +\n",
    "  geom_point(color = '#E41A1C', size = 3) +\n",
    "  labs(x = '年份', y = '文献数量') +\n",
    "  theme_minimal() +\n",
    "  theme(panel.grid.minor = element_blank())\n",
    "```\n\n",
    "### 疾病关联强度Top10\n",
    "```{r conditions, echo=FALSE}\n",
    "stats$condition_association %>%\n",
    "  select(疾病 = conditions, 关联强度 = association_strength, 研究数量 = n) %>%\n",
    "  knitr::kable(format = 'pipe', digits = 2)\n",
    "```\n"
  )
  
  writeLines(rmd_content, "professional_report.Rmd")
  
  if (!is.null(output_pdf)) {
    render("professional_report.Rmd", output_file = output_pdf, output_format = "pdf_document")
    message("PDF报告已生成: ", output_pdf)
  }
  
  if (!is.null(output_html)) {
    render("professional_report.Rmd", output_file = output_html, output_format = "html_document")
    message("HTML报告已生成: ", output_html)
  }
  
  file.remove("professional_report.Rmd")
}
