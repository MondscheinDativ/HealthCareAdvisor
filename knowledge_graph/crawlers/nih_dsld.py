import requests
import csv
import os
import time
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET

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

DSLD_API = "https://dsld.nlm.nih.gov/dsld/api"

def get_supplement_details(supplement_name, retries=3):
    params = {"name": supplement_name, "format": "xml"}
    
    for attempt in range(retries):
        try:
            # 检查DNS解析
            socket.getaddrinfo("dsld.nlm.nih.gov", 443)
            
            response = requests.get(
                DSLD_API,
                params=params,
                timeout=30,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            )
            response.raise_for_status()
            
            # 处理可能的空响应
            if not response.content:
                logger.warning(f"Empty response for {supplement_name}, attempt {attempt+1}")
                time.sleep(2 ** attempt)  # 指数退避
                continue
            
            # 更健壮的XML解析
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"XML parse error for {supplement_name}: {str(e)}")
                # 尝试解码内容
                content_str = response.content.decode('utf-8', errors='ignore')
                if "error" in content_str.lower():
                    logger.error(f"API error response: {content_str[:200]}")
                time.sleep(2 ** attempt)
                continue
            
            details = []
            
            # 检查是否有产品数据
            products = root.findall(".//product")
            if not products:
                logger.info(f"No products found for {supplement_name}")
                return []
            
            for product in products:
                try:
                    name_elem = product.find("name")
                    manufacturer_elem = product.find("manufacturer")
                    
                    # 提取成分
                    ingredients = []
                    for ing in product.findall(".//ingredient"):
                        name = ing.find("name").text if ing.find("name") is not None else "Unknown"
                        amount_elem = ing.find("amount")
                        amount = amount_elem.text if amount_elem is not None and amount_elem.text else "Unknown"
                        ingredients.append(f"{name} ({amount})")
                    
                    # 提取健康声明
                    health_claims = []
                    for claim in product.findall(".//health_claim"):
                        if claim.text and claim.text.strip():
                            health_claims.append(claim.text.strip())
                    
                    details.append({
                        "supplement": supplement_name,
                        "product_name": name_elem.text if name_elem is not None and name_elem.text else "Unknown",
                        "manufacturer": manufacturer_elem.text if manufacturer_elem is not None and manufacturer_elem.text else "Unknown",
                        "ingredients": "; ".join(ingredients),
                        "health_claims": "; ".join(health_claims)
                    })
                except Exception as e:
                    logger.error(f"Error parsing product for {supplement_name}: {str(e)}")
                    continue
            
            return details
        
        except (requests.exceptions.RequestException, socket.gaierror) as e:
            logger.error(f"Attempt {attempt+1} failed for {supplement_name}: {str(e)}")
            time.sleep(min(2 ** attempt, 30))
        except Exception as e:
            logger.error(f"Unexpected error for {supplement_name}: {str(e)}")
            time.sleep(min(2 ** attempt, 30))
    
    return []  # 所有重试失败后返回空列表

def main():
    supplements = load_supplements()
    
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(base_dir, 'knowledge_graph', 'data', 'raw', 'nih_dsld')
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Starting NIH DSLD crawl for {len(supplements)} supplements")
    
    with ThreadPoolExecutor(max_workers=2) as executor:  # 进一步减少并发数
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
                    logger.info(f"Saved {len(data)} products for {supplement}")
                else:
                    logger.warning(f"No data found for {supplement}")
            except Exception as e:
                logger.error(f"Error processing {supplement}: {str(e)}")
            finally:
                time.sleep(2)  # 增加API限速时间

if __name__ == "__main__":
    main()
