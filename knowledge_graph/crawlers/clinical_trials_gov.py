import requests
import csv
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("clinical_trials.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 项目路径工具
def get_project_root():
    """获取项目根目录的可靠方法"""
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

def safe_api_request(url, params, retries=3, timeout=30):
    """带重试和错误处理的API请求"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json'
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(
                url, 
                params=params, 
                headers=headers, 
                timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            if status == 404:
                logger.error(f"404 未找到: {url}")
                return None
            elif status == 429:
                wait = min(2 ** attempt, 60)
                logger.warning(f"请求过多，等待 {wait} 秒后重试...")
                time.sleep(wait)
            else:
                logger.error(f"HTTP错误 {status}: {str(e)}")
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.error(f"网络错误: {str(e)}")
            wait = min(2 ** attempt, 30)
            time.sleep(wait)
        except Exception as e:
            logger.error(f"未知错误: {str(e)}")
            wait = min(2 ** attempt, 30)
            time.sleep(wait)
    
    logger.error(f"请求失败，重试 {retries} 次后放弃")
    return None

def fetch_trials(supplement):
    """获取临床试验数据"""
    encoded_supplement = quote(supplement, encoding='utf-8')
    expr = f'"{encoded_supplement}"[Supplement] AND "dietary supplement"[Intervention]'
    url = "https://clinicaltrials.gov/api/query/full_studies"
    
    params = {
        "expr": expr,
        "min_rnk": 1,
        "max_rnk": 100,
        "fmt": "json"
    }
    
    response = safe_api_request(url, params, timeout=45)
    if not response:
        logger.warning(f"无法获取 {supplement} 的数据")
        return supplement, None
    
    try:
        data = response.json()
        n_studies = data.get("FullStudiesResponse", {}).get("NStudiesFound", 0)
        
        if n_studies == 0:
            logger.info(f"{supplement} 无相关研究")
            return supplement, None
        
        studies = data.get("FullStudiesResponse", {}).get("FullStudies", [])
        return supplement, studies
    except Exception as e:
        logger.error(f"解析 {supplement} 数据失败: {str(e)}")
        return supplement, None

def parse_study(study):
    """解析单个研究数据"""
    try:
        protocol = study["ProtocolSection"]
        id_module = protocol["IdentificationModule"]
        status_module = protocol["StatusModule"]
        
        # 条件
        conditions_module = protocol.get("ConditionsModule", {})
        conditions = conditions_module.get("ConditionList", {}).get("Condition", [])
        
        # 干预措施
        interventions = []
        arms_module = protocol.get("ArmsInterventionsModule", {})
        intervention_list = arms_module.get("InterventionList", {}).get("Intervention", [])
        for i in intervention_list:
            name = i.get("InterventionName", "未命名干预")
            itype = i.get("InterventionType", "未知类型")
            interventions.append(f"{name} ({itype})")
        
        # 主要结果
        primary_outcome = "未指定"
        outcomes_module = protocol.get("OutcomesModule", {})
        if outcomes_module:
            primary_outcome_list = outcomes_module.get("PrimaryOutcomeList", {}).get("PrimaryOutcome", [])
            if primary_outcome_list:
                primary_outcome = primary_outcome_list[0].get("PrimaryOutcomeMeasure", "未指定")
        
        return {
            "nct_id": id_module.get("NCTId", "无ID"),
            "title": id_module.get("OfficialTitle", "无标题"),
            "status": status_module.get("OverallStatus", "状态未知"),
            "conditions": "; ".join(conditions),
            "interventions": "; ".join(interventions),
            "primary_outcomes": primary_outcome
        }
    except Exception as e:
        logger.error(f"解析研究失败: {str(e)}")
        return None

def process_supplement(supplement):
    """处理单个补剂"""
    logger.info(f"开始处理: {supplement}")
    supp, studies = fetch_trials(supplement)
    
    if not studies:
        logger.warning(f"{supplement} 无有效研究")
        return None
    
    valid_studies = []
    for s in studies:
        study_data = s.get("Study")
        if study_data:
            parsed = parse_study(study_data)
            if parsed:
                valid_studies.append(parsed)
    
    if not valid_studies:
        logger.warning(f"{supplement} 无有效研究数据")
        return None
    
    return {
        "supplement": supplement,
        "studies": valid_studies
    }

def main():
    supplements = load_supplements()
    if not supplements:
        logger.error("未加载任何补剂，程序终止")
        return
    
    root = get_project_root()
    output_dir = os.path.join(root, 'knowledge_graph', 'data', 'raw', 'clinical_trials')
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")
    
    logger.info(f"开始爬取 {len(supplements)} 种补剂的临床试验数据")
    
    # 使用单线程确保稳定性
    for supplement in supplements:
        try:
            result = process_supplement(supplement)
            if not result:
                continue
                
            output_path = os.path.join(output_dir, f"{result['supplement']}.csv")
            with open(output_path, "w", newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=result['studies'][0].keys())
                writer.writeheader()
                writer.writerows(result['studies'])
            
            logger.info(f"保存 {len(result['studies'])} 项研究: {result['supplement']}")
            time.sleep(5)  # 严格遵守API限制
        except Exception as e:
            logger.error(f"处理 {supplement} 时出错: {str(e)}")
    
    logger.info("临床试验数据爬取完成")

if __name__ == "__main__":
    main()
