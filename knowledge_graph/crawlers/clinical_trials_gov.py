import requests
import csv
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 读取补剂列表
def load_supplements():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录
    base_dir = os.path.dirname(base_dir)  # 上移一级到knowledge_graph
    config_path = os.path.join(base_dir, 'config', 'supplements.txt')
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def fetch_trials(supplement, retries=5):
    # 正确编码中文参数
    encoded_supplement = quote(supplement, encoding='utf-8')
    
    # 构建查询表达式
    expr = f'"{encoded_supplement}"[Supplement] AND "dietary supplement"[Intervention]'
    
    url = "https://clinicaltrials.gov/api/query/full_studies"
    params = {
        "expr": expr,
        "min_rnk": 1,
        "max_rnk": 100,
        "fmt": "json"
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(
                url, 
                params=params, 
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            )
            response.raise_for_status()
            
            # 检查是否有有效数据
            data = response.json()
            if not data.get("FullStudiesResponse", {}).get("FullStudies"):
                logger.warning(f"No studies found for {supplement}")
                return supplement, None
                
            return supplement, data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"404 Not Found for {supplement}: {e.response.url}")
                # 尝试不同编码方式
                expr = f'"{supplement}"[Supplement] AND "dietary supplement"[Intervention]'
                params["expr"] = expr
                logger.info(f"Retrying with unencoded supplement name")
            else:
                logger.error(f"HTTP error for {supplement}: {str(e)}")
            
            wait_time = min(2 ** attempt, 30)  # 指数退避，最大30秒
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed for {supplement}: {str(e)}")
            wait_time = min(2 ** attempt, 30)  # 指数退避，最大30秒
            time.sleep(wait_time)
    
    return supplement, None

def parse_study(study):
    try:
        protocol = study["ProtocolSection"]
        return {
            "nct_id": protocol["IdentificationModule"]["NCTId"],
            "title": protocol["IdentificationModule"]["OfficialTitle"],
            "status": protocol["StatusModule"]["OverallStatus"],
            "conditions": ", ".join(protocol["ConditionsModule"].get("ConditionList", {}).get("Condition", [])),
            "interventions": ", ".join([
                f"{i['InterventionName']} ({i['InterventionType']})" 
                for i in protocol["ArmsInterventionsModule"]["InterventionList"]["Intervention"]
            ]),
            "primary_outcomes": protocol["OutcomesModule"]["PrimaryOutcomeList"]["PrimaryOutcome"][0]["PrimaryOutcomeMeasure"]
        }
    except (KeyError, TypeError):
        return None

def main():
    supplements = load_supplements()
    base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录
    base_dir = os.path.dirname(base_dir)  # 上移一级到knowledge_graph
    output_dir = os.path.join(base_dir, 'data', 'raw', 'clinical_trials')
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting ClinicalTrials.gov crawl for {len(supplements)} supplements")

    with ThreadPoolExecutor(max_workers=3) as executor:  # 减少并发数
        future_to_supp = {
            executor.submit(fetch_trials, supp): supp
            for supp in supplements
        }
        
        for future in as_completed(future_to_supp):
            supplement = future_to_supp[future]
            try:
                supp, data = future.result()
                if not data:
                    logger.warning(f"No data for {supplement}")
                    continue
                    
                studies = data.get("FullStudiesResponse", {}).get("FullStudies", [])
                valid_studies = [parse_study(s["Study"]) for s in studies]
                valid_studies = [s for s in valid_studies if s]
                
                if valid_studies:
                    output_path = os.path.join(output_dir, f"{supplement}.csv")
                    with open(output_path, "w", newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=valid_studies[0].keys())
                        writer.writeheader()
                        writer.writerows(valid_studies)
                    logger.info(f"Saved {len(valid_studies)} studies for {supplement}")
                else:
                    logger.warning(f"No valid studies for {supplement}")
                
                time.sleep(3)  # 遵守API限速
                
            except Exception as e:
                logger.error(f"Error processing {supplement}: {str(e)}")

if __name__ == "__main__":
    main()
