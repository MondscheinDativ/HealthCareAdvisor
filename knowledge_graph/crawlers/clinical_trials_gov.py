import requests
import csv
import time
import os
from bs4 import BeautifulSoup

# 从重点补剂列表读取关键词
SUPPLEMENTS = ["PQQ", "NMN", "镁", "维生素D3", "CoQ10", "NAD+"]  # 示例列表

def fetch_trials(supplement):
    url = "https://clinicaltrials.gov/api/query/full_studies"
    params = {
        "expr": f"{supplement} dietary supplement",
        "min_rnk": 1,
        "max_rnk": 50,
        "fmt": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {supplement}: {str(e)}")
        return None

def parse_study(study):
    try:
        protocol = study["ProtocolSection"]
        return {
            "nct_id": protocol["IdentificationModule"]["NCTId"],
            "title": protocol["IdentificationModule"]["OfficialTitle"],
            "status": protocol["StatusModule"]["OverallStatus"],
            "conditions": ", ".join(protocol["ConditionsModule"]["ConditionList"]["Condition"]),
            "interventions": ", ".join([
                f"{i['InterventionName']} ({i['InterventionType']})" 
                for i in protocol["ArmsInterventionsModule"]["InterventionList"]["Intervention"]
            ]),
            "primary_outcomes": protocol["OutcomesModule"]["PrimaryOutcomeList"]["PrimaryOutcome"][0]["PrimaryOutcomeMeasure"]
        }
    except KeyError:
        return None

def main():
    os.makedirs("../data/raw/clinical_trials", exist_ok=True)
    
    for supplement in SUPPLEMENTS:
        print(f"Fetching data for: {supplement}")
        data = fetch_trials(supplement)
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
        
        time.sleep(5)  # 遵守API限速

if __name__ == "__main__":
    main()
