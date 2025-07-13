import requests
import csv
import xml.etree.ElementTree as ET

DSLD_API = "https://dsld.nlm.nih.gov/dsld/api"

def get_supplement_details(supplement_name):
    params = {"name": supplement_name, "format": "xml"}
    response = requests.get(DSLD_API, params=params)
    root = ET.fromstring(response.content)
    
    details = []
    for product in root.findall(".//product"):
        details.append({
            "supplement": supplement_name,
            "product_name": product.find("name").text,
            "manufacturer": product.find("manufacturer").text,
            "ingredients": "; ".join([
                f"{ing.find('name').text} ({ing.find('amount').text})" 
                for ing in product.findall(".//ingredient")
            ]),
            "health_claims": "; ".join([
                claim.text for claim in product.findall(".//health_claim")
            ])
        })
    return details

def main():
    # 从重点列表获取补剂名称
    for supplement in SUPPLEMENTS:  
        data = get_supplement_details(supplement)
        with open(f"../data/raw/nih_dsld/{supplement}.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

if __name__ == "__main__":
    main()
