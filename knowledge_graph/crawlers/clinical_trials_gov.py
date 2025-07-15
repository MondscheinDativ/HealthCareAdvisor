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

def load_supplements():
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(base_dir, 'knowledge_graph', 'config', 'supplements.txt')
    logger.info(f"Loading supplements from: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def fetch_trials(supplement, retries=3):
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
                timeout=45,  # 增加超时时间
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            )
            response.raise_for_status()
            
            data = response.json()
            n_studies = data.get("FullStudiesResponse", {}).get("NStudiesFound", 0)
            
            if n_studies == 0:
                logger.info(f"No studies found for {supplement}")
                return supplement, None
            
            studies = data.get("FullStudiesResponse", {}).get("FullStudies", [])
            if not studies:
                logger.warning(f"API returned no studies for {supplement} despite {n_studies} found")
                return supplement, None
            
            return supplement, data
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"404 Not Found for {supplement}: {e.response.url}")
            else:
                logger.error(f"HTTP error for {supplement}: {str(e)}")
            wait_time = min(2 ** attempt, 30)
            time.sleep(wait_time)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"Network error for {supplement}: {str(e)}")
            wait_time = min(2 ** attempt, 30)
            time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed for {supplement}: {str(e)}")
            wait_time = min(2 ** attempt, 30)
            time.sleep(wait_time)
    
    return supplement, None

def parse_study(study):
    try:
        protocol = study["ProtocolSection"]
        id_module = protocol["IdentificationModule"]
        status_module = protocol["StatusModule"]
        
        # 更健壮的条件提取
        conditions_module = protocol.get("ConditionsModule", {})
        conditions = conditions_module.get("ConditionList", {}).get("Condition", [])
        conditions_str = ", ".join(conditions) if conditions else "Not specified"
        
        # 更健壮的干预措施提取
        interventions = []
        arms_module = protocol.get("ArmsInterventionsModule", {})
        intervention_list = arms_module.get("InterventionList", {}).get("Intervention", [])
        for i in intervention_list:
            name = i.get("InterventionName", "Unnamed intervention")
            itype = i.get("InterventionType", "Unknown type")
            interventions.append(f"{name} ({itype})")
        
        # 更健壮的主要结果提取
        outcomes_module = protocol.get("OutcomesModule", {})
        primary_outcome_list = outcomes_module.get("PrimaryOutcomeList", {}).get("PrimaryOutcome", [])
        primary_outcome = primary_outcome_list[0]["PrimaryOutcomeMeasure"] if primary_outcome_list else "Not specified"
        
        return {
            "nct_id": id_module.get("NCTId", "No NCT ID"),
            "title": id_module.get("OfficialTitle", "No title available"),
            "status": status_module.get("OverallStatus", "Status unknown"),
            "conditions": conditions_str,
            "interventions": "; ".join(interventions),
            "primary_outcomes": primary_outcome
        }
    
    except (KeyError, TypeError) as e:
        logger.error(f"Error parsing study: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing study: {str(e)}")
        return None

def main():
    supplements = load_supplements()
    
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(base_dir, 'knowledge_graph', 'data', 'raw', 'clinical_trials')
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting ClinicalTrials.gov crawl for {len(supplements)} supplements")
    
    with ThreadPoolExecutor(max_workers=2) as executor:  # 进一步减少并发数
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
                if not studies:
                    logger.warning(f"No studies in response for {supplement}")
                    continue
                
                valid_studies = []
                for s in studies:
                    study_data = s.get("Study")
                    if study_data:
                        parsed = parse_study(study_data)
                        if parsed:
                            valid_studies.append(parsed)
                
                if valid_studies:
                    output_path = os.path.join(output_dir, f"{supplement}.csv")
                    with open(output_path, "w", newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=valid_studies[0].keys())
                        writer.writeheader()
                        writer.writerows(valid_studies)
                    logger.info(f"Saved {len(valid_studies)} studies for {supplement}")
                else:
                    logger.warning(f"No valid studies for {supplement}")
                
                time.sleep(4)  # 增加API限速时间
            
            except Exception as e:
                logger.error(f"Error processing {supplement}: {str(e)}")

if __name__ == "__main__":
    main()
