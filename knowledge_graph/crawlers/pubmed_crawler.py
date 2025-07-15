import requests
import csv
import os
import time
import logging
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_supplements():
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, 'knowledge_graph', 'config', 'supplements.txt')
    logger.info(f"Loading supplements from: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def fetch_pubmed(supplement):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base_url}esearch.fcgi"
    fetch_url = f"{base_url}efetch.fcgi"
    
    # 更健壮的搜索参数
    search_params = {
        "db": "pubmed",
        "term": f'"{supplement}"[Title/Abstract] AND ("dietary supplement"[MeSH] OR "dietary supplements"[MeSH])',
        "retmax": 50,
        "retmode": "json"
    }
    
    try:
        search_res = requests.get(search_url, params=search_params, timeout=30)
        search_res.raise_for_status()
        search_data = search_res.json()
        
        # 更健壮的结果检查
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            logger.warning(f"No articles found for {supplement}")
            return supplement, []
        
        # 获取文章详情
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        fetch_res = requests.get(fetch_url, params=fetch_params, timeout=30)
        fetch_res.raise_for_status()
        
        soup = BeautifulSoup(fetch_res.content, 'xml')
        articles = []
        
        for article in soup.find_all('PubmedArticle'):
            try:
                title = article.find('ArticleTitle')
                title = title.text if title and title.text else "No Title"
                
                abstract = article.find('AbstractText')
                abstract = abstract.text if abstract and abstract.text else "No Abstract"
                
                journal = article.find('Journal')
                journal_title = journal.find('Title').text if journal and journal.find('Title') else "Unknown Journal"
                
                pub_date = article.find('PubDate')
                year = pub_date.find('Year').text if pub_date and pub_date.find('Year') else "Unknown"
                month = pub_date.find('Month').text if pub_date and pub_date.find('Month') else ""
                pub_date_str = f"{year}-{month}" if month else year
                
                pmid = article.find('PMID')
                pmid = pmid.text if pmid else "No PMID"
                
                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract,
                    "journal": journal_title,
                    "pub_date": pub_date_str
                })
            except Exception as e:
                logger.error(f"Error parsing article for {supplement}: {str(e)}")
                continue
        
        return supplement, articles
    
    except Exception as e:
        logger.error(f"Error fetching PubMed data for {supplement}: {str(e)}")
        return supplement, []

def main():
    supplements = load_supplements()
    
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(base_dir, 'knowledge_graph', 'data', 'raw', 'pubmed')
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting PubMed crawl for {len(supplements)} supplements")
    
    with ThreadPoolExecutor(max_workers=3) as executor:  # 减少并发数
        results = list(executor.map(fetch_pubmed, supplements))
    
    for supplement, articles in results:
        if articles:
            output_path = os.path.join(output_dir, f"{supplement}.csv")
            with open(output_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=articles[0].keys())
                writer.writeheader()
                writer.writerows(articles)
            logger.info(f"Saved {len(articles)} articles for {supplement}")
        else:
            logger.warning(f"No articles found for {supplement}")
        
        time.sleep(3)  # 遵守API限速

if __name__ == "__main__":
    main()
