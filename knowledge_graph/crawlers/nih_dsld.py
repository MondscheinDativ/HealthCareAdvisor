import requests
import csv
import os
import time
import logging
from lxml import etree  # 替换XML解析器（提高兼容性）

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("nih_dsld.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_project_root():
    if 'GITHUB_WORKSPACE' in os.environ:
        return os.environ['GITHUB_WORKSPACE']
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current_dir))

def load_supplements():
    root = get_project_root()
    config_path = os.path.join(root, 'knowledge_graph', 'config', 'supplements.txt')
    logger.info(f"加载补剂列表从: {config_path}")
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f.readlines() if line.strip()]

# 复用补剂中英文映射表（核心修改）
SUPPLEMENT_MAPPING = {
    "复合B族": "B-complex",
    "维生素C": "Vitamin C",
    "锌": "Zinc",
    # ...（同clinical_trials_gov.py中的完整映射表）
    "水飞蓟宾": "Silybin"
}

DSLD_API = "https://dsld.nlm.nih.gov/dsld/api"

def safe_api_request(url, params, retries=3, timeout=30):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/xml'
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 404:
                logger.error(f"404 未找到: {url}")
                return None
            elif status == 429:
                wait = min(2 **attempt, 60)
                logger.warning(f"请求过多，等待 {wait} 秒后重试...")
                time.sleep(wait)
            else:
                logger.error(f"HTTP错误 {status}: {str(e)}")
                wait = min(2** attempt, 30)
                time.sleep(wait)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"网络错误: {str(e)}")
            wait = min(2 **attempt, 30)
            time.sleep(wait)
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            wait = min(2** attempt, 30)
            time.sleep(wait)
    logger.error(f"请求失败，重试 {retries} 次后放弃")
    return None

def get_supplement_details(supplement_name):
    # 使用英文名称查询（核心修改）
    supplement_en = SUPPLEMENT_MAPPING.get(supplement_name, supplement_name)
    params = {"name": supplement_en, "format": "xml"}
    logger.info(f"查询NIH DSLD: {DSLD_API}?name={supplement_en}")  # 新增日志：输出查询URL
    response = safe_api_request(DSLD_API, params, timeout=45)
    if not response:
        logger.warning(f"无法获取 {supplement_name} 的数据")
        return []
    if not response.content:
        logger.warning(f"空响应: {supplement_name}")
        return []
    try:
        # 使用lxml解析XML（提高兼容性，核心修改）
        root = etree.fromstring(response.content)
    except etree.XMLSyntaxError as e:
        logger.error(f"XML解析失败: {str(e)}")
        return []
    details = []
    products = root.findall(".//product")
    if not products:
        logger.info(f"{supplement_name}（{supplement_en}）无相关产品")
        return []
    for product in products:
        try:
            name_elem = product.find("name")
            product_name = name_elem.text if name_elem is not None and name_elem.text else "未命名产品"
            manufacturer_elem = product.find("manufacturer")
            manufacturer = manufacturer_elem.text if manufacturer_elem is not None and manufacturer_elem.text else "未知制造商"
            ingredients = []
            for ing in product.findall(".//ingredient"):
                name_elem = ing.find("name")
                name = name_elem.text if name_elem is not None else "未知成分"
                amount_elem = ing.find("amount")
                amount = amount_elem.text if amount_elem is not None else "未知含量"
                ingredients.append(f"{name} ({amount})")
            health_claims = []
            for claim in product.findall(".//health_claim"):
                if claim.text and claim.text.strip():
                    health_claims.append(claim.text.strip())
            details.append({
                "supplement": supplement_name,
                "product_name": product_name,
                "manufacturer": manufacturer,
                "ingredients": "; ".join(ingredients),
                "health_claims": "; ".join(health_claims)
            })
        except Exception as e:
            logger.error(f"解析产品失败: {str(e)}")
            continue
    return details

def main():
    supplements = load_supplements()
    if not supplements:
        logger.error("未加载任何补剂，程序终止")
        return
    root = get_project_root()
    output_dir = os.path.join(root, 'knowledge_graph', 'data', 'raw', 'nih_dsld')
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"开始爬取 {len(supplements)} 种补剂的NIH DSLD数据")
    for supplement in supplements:
        try:
            logger.info(f"处理: {supplement}")
            data = get_supplement_details(supplement)
            if not data:
                logger.warning(f"{supplement} 无有效数据")
                continue
            output_path = os.path.join(output_dir, f"{supplement}.csv")
            with open(output_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            logger.info(f"保存 {len(data)} 个产品: {supplement}")
            time.sleep(5)
        except Exception as e:
            logger.error(f"处理 {supplement} 时出错: {str(e)}")
    logger.info("NIH DSLD数据爬取完成")

if __name__ == "__main__":
    main()
