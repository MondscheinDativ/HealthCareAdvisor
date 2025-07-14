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
    # 添加路径处理
    base_dir = os.path.dirname(os.path.abspath(__file__))  # 当前脚本目录
    base_dir = os.path.dirname(base_dir)  # 上移一级到knowledge_graph
    output_dir = os.path.join(base_dir, 'data', 'raw', 'nih_dsld')
    os.makedirs(output_dir, exist_ok=True)
    
    # 修改文件保存路径
    for supplement in SUPPLEMENTS:
        data = get_supplement_details(supplement)
        output_path = os.path.join(output_dir, f"{supplement}.csv")  # 使用新路径

if __name__ == "__main__":
    main()
