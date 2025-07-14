import requests
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET

# 读取补剂列表 - 与其他爬虫一致
def load_supplements():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录
    base_dir = os.path.dirname(base_dir)  # 上移一级到knowledge_graph
    config_path = os.path.join(base_dir, 'config', 'supplements.txt')
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

DSLD_API = "https://dsld.nlm.nih.gov/dsld/api"

def get_supplement_details(supplement_name, retries=3):
    params = {"name": supplement_name, "format": "xml"}
    
    for attempt in range(retries):
        try:
            response = requests.get(DSLD_API, params=params, timeout=30)
            response.raise_for_status()
            
            # 处理可能的空响应
            if not response.content:
                print(f"Empty response for {supplement_name}, attempt {attempt+1}")
                return []
                
            root = ET.fromstring(response.content)
            details = []
            
            for product in root.findall(".//product"):
                # 安全获取元素值
                name_elem = product.find("name")
                manufacturer_elem = product.find("manufacturer")
                
                # 提取成分
                ingredients = []
                for ing in product.findall(".//ingredient"):
                    name = ing.find("name").text if ing.find("name") is not None else "Unknown"
                    amount = ing.find("amount").text if ing.find("amount") is not None else "Unknown"
                    ingredients.append(f"{name} ({amount})")
                
                # 提取健康声明
                health_claims = [claim.text for claim in product.findall(".//health_claim") if claim.text]
                
                details.append({
                    "supplement": supplement_name,
                    "product_name": name_elem.text if name_elem is not None else "Unknown",
                    "manufacturer": manufacturer_elem.text if manufacturer_elem is not None else "Unknown",
                    "ingredients": "; ".join(ingredients),
                    "health_claims": "; ".join(health_claims)
                })
                
            return details
            
        except Exception as e:
            print(f"Attempt {attempt+1} failed for {supplement_name}: {str(e)}")
            time.sleep(5)
    
    return []  # 所有重试失败后返回空列表

def main():
    supplements = load_supplements()
    
    # 设置输出目录
    base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录
    base_dir = os.path.dirname(base_dir)  # 上移一级到knowledge_graph
    output_dir = os.path.join(base_dir, 'data', 'raw', 'nih_dsld')
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Starting NIH DSLD crawl for {len(supplements)} supplements")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_supp = {
            executor.submit(get_supplement_details, supp): supp
            for supp in supplements
        }
        
        for future in as_completed(future_to_supp):
            supplement = future_to_supp[future]
            try:
                data = future.result()
                if data:
                    output_path = os.path.join(output_dir, f"{supplement}.csv")
                    with open(output_path, "w", newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
                    print(f"Saved {len(data)} products for {supplement}")
                else:
                    print(f"No data found for {supplement}")
                
                time.sleep(1)  # 遵守API限速
                
            except Exception as e:
                print(f"Error processing {supplement}: {str(e)}")

if __name__ == "__main__":
    main()
