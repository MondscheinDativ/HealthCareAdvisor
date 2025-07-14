import requests
import csv
import os
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# 修复路径
def load_supplements():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, 'config', 'supplements.txt')
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def fetch_pubmed(supplement):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base_url}esearch.fcgi"
    fetch_url = f"{base_url}efetch.fcgi"
    
    # 搜索相关文章
    search_params = {
        "db": "pubmed",
        "term": f'{supplement}[Title/Abstract] AND ("dietary supplement"[MeSH] OR "dietary supplements"[MeSH])',
        "retmax": 50,
        "retmode": "json"
    }
    
    try:
        search_res = requests.get(search_url, params=search_params)
        search_data = search_res.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not id_list:
            return supplement, []
        
        # 获取文章详情
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        
        fetch_res = requests.get(fetch_url, params=fetch_params)
        soup = BeautifulSoup(fetch_res.content, 'xml')
        
        articles = []
        for article in soup.find_all('PubmedArticle'):
            title = article.find('ArticleTitle')
            title = title.text if title else "No Title"
            
            abstract = article.find('AbstractText')
            abstract = abstract.text if abstract else "No Abstract"
            
            journal = article.find('Title')
            journal = journal.text if journal else "Unknown Journal"
            
            pub_date = article.find('PubDate')
            pub_date = pub_date.text if pub_date else "Unknown Date"
            
            articles.append({
                "pmid": article.find('PMID').text,
                "title": title,
                "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract,
                "journal": journal,
                "pub_date": pub_date
            })
        
        return supplement, articles
    except Exception as e:
        print(f"Error for {supplement}: {str(e)}")
        return supplement, []

def main():
    supplements = load_supplements()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(base_dir, 'data', 'raw', 'pubmed')
    os.makedirs(output_dir, exist_ok=True)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(fetch_pubmed, supplements)
        
        for supplement, articles in results:
            if articles:
                output_path = os.path.join(output_dir, f"{supplement}.csv")
                with open(output_path, "w", newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=articles[0].keys())
                    writer.writeheader()
                    writer.writerows(articles)
            time.sleep(3)  # 遵守API限速

if __name__ == "__main__":
    main()
