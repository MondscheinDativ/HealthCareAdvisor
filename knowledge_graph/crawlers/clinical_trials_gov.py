import requests
import csv
import time
import os
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor, as_completed

# 读取补剂列表
def load_supplements():
    with open('../config/supplements.txt', 'r') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

def fetch_trials(supplement, retries=3):
    url = "https://clinicaltrials.gov/api/query/full_studies"
    params = {
        "expr": f'"{supplement}"[Supplement] AND "dietary supplement"[Intervention]',
        "min_rnk": 1,
        "max_rnk": 100,
        "fmt": "json"
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return supplement, response.json()
        except Exception as e:
            print(f"Attempt {attempt+1} failed for {supplement}: {str(e)}")
            time.sleep(5)
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
    except KeyError:
        return None

def main():
    supplements = load_supplements()
    os.makedirs("../data/raw/clinical_trials", exist_ok=True)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_supp = {
            executor.submit(fetch_trials, supp): supp 
            for supp in supplements
        }
        
        for future in as_completed(future_to_supp):
            supplement = future_to_supp[future]
            try:
                supp, data = future.result()
                if not data:
                    continue
                    
                studies = data.get("FullStudiesResponse", {}).get("FullStudies", [])
                valid_studies = [parse_study(s["Study"]) for s in studies]
                valid_studies = [s for s in valid_studies if s]
                
                if valid_studies:
                    with open(f"../data/raw/clinical_trials/{supplement}.csv", "w", newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=valid_studies[0].keys())
                        writer.writeheader()
                        writer.writerows(valid_studies)
                
                time.sleep(2)  # 遵守API限速
            except Exception as e:
                print(f"Error processing {supplement}: {str(e)}")

if __name__ == "__main__":
    main()
