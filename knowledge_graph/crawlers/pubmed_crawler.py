import requests
import csv
import os
import time
import logging
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pubmed.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_project_root():
    if 'GITHUB_WORKSPACE' in os.environ:
        return os.environ['GITHUB_WORKSPACE']
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current_dir))

def load_supplements():
    root = get_project_root()
    config_path = os.path.join(root, 'knowledge_graph', 'config', 'supplements.txt')
    logger.info(f"加载补剂列表从: {config_path}")
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

# 复用补剂中英文映射表（核心修改）
SUPPLEMENT_MAPPING = {
    "复合B族": "B-complex",
    "维生素C": "Vitamin C",
    "锌": "Zinc",
    # ...（同clinical_trials_gov.py中的完整映射表）
    "水飞蓟宾": "Silybin"
}

def safe_api_request(url, params, retries=3, timeout=30):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json'
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 404:
                logger.error(f"404 未找到: {url}")
                return None
            elif status == 429:
                wait = min(2 **attempt, 60)
                logger.warning(f"请求过多，等待 {wait} 秒后重试...")
                time.sleep(wait)
            else:
                logger.error(f"HTTP错误 {status}: {str(e)}")
                wait = min(2** attempt, 30)
                time.sleep(wait)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"网络错误: {str(e)}")
            wait = min(2 **attempt, 30)
            time.sleep(wait)
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            wait = min(2** attempt, 30)
            time.sleep(wait)
    logger.error(f"请求失败，重试 {retries} 次后放弃")
    return None

def fetch_pubmed(supplement):
    # 使用英文名称查询（核心修改）
    supplement_en = SUPPLEMENT_MAPPING.get(supplement, supplement)
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base_url}esearch.fcgi"
    # 修正查询术语：使用正确的MeSH术语和逻辑（核心修改）
    term = f'"{supplement_en}"[Title/Abstract] AND "Dietary Supplements"[MeSH Major Topic]'
    search_params = {
        "db": "pubmed",
        "term": term,
        "retmax": 50,
        "retmode": "json"
    }
    logger.info(f"查询PubMed: {search_url}?db=pubmed&term={term}")  # 新增日志：输出查询URL
    search_res = safe_api_request(search_url, search_params, timeout=45)
    if not search_res:
        logger.warning(f"搜索 {supplement} 失败")
        return supplement, []
    try:
        search_data = search_res.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            logger.info(f"{supplement}（{supplement_en}）无相关文章")
            return supplement, []
    except Exception as e:
        logger.error(f"解析搜索结果失败: {str(e)}")
        return supplement, []
    fetch_url = f"{base_url}efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml"
    }
    fetch_res = safe_api_request(fetch_url, fetch_params, timeout=60)
    if not fetch_res:
        logger.warning(f"获取文章详情失败: {supplement}")
        return supplement, []
    try:
        soup = BeautifulSoup(fetch_res.content, 'xml')
        articles = []
        for article in soup.find_all('PubmedArticle'):
            try:
                title_elem = article.find('ArticleTitle')
                title = title_elem.text if title_elem else "无标题"
                abstract_elem = article.find('AbstractText')
                abstract = abstract_elem.text if abstract_elem else "无摘要"
                if len(abstract) > 500:
                    abstract = abstract[:500] + "..."
                journal_elem = article.find('Journal')
                journal_title = "未知期刊"
                if journal_elem:
                    title_elem = journal_elem.find('Title')
                    journal_title = title_elem.text if title_elem else "未知期刊"
                pub_date_elem = article.find('PubDate')
                pub_date = "未知日期"
                if pub_date_elem:
                    year_elem = pub_date_elem.find('Year')
                    month_elem = pub_date_elem.find('Month')
                    year = year_elem.text if year_elem else "年份未知"
                    month = month_elem.text if month_elem else ""
                    pub_date = f"{year}-{month}" if month else year
                pmid_elem = article.find('PMID')
                pmid = pmid_elem.text if pmid_elem else "无PMID"
                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract,
                    "journal": journal_title,
                    "pub_date": pub_date
                })
            except Exception as e:
                logger.error(f"解析文章失败: {str(e)}")
                continue
        return supplement, articles
    except Exception as e:
        logger.error(f"解析文章列表失败: {str(e)}")
        return supplement, []

def main():
    supplements = load_supplements()
    if not supplements:
        logger.error("未加载任何补剂，程序终止")
        return
    root = get_project_root()
    output_dir = os.path.join(root, 'knowledge_graph', 'data', 'raw', 'pubmed')
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"开始爬取 {len(supplements)} 种补剂的PubMed数据")
    for supplement in supplements:
        try:
            logger.info(f"处理: {supplement}")
            supp, articles = fetch_pubmed(supplement)
            if not articles:
                logger.warning(f"{supplement} 无有效文章")
                continue
            output_path = os.path.join(output_dir, f"{supplement}.csv")
            with open(output_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=articles[0].keys())
                writer.writeheader()
                writer.writerows(articles)
            logger.info(f"保存 {len(articles)} 篇文章: {supplement}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"处理 {supplement} 时出错: {str(e)}")
    logger.info("PubMed数据爬取完成")

if __name__ == "__main__":
    main()
