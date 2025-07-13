from src.crawler import SupplementCrawler
from src.data_cleaner import SupplementDataCleaner
from src.graph_builder import KnowledgeGraphBuilder
from src.conflict_detector import ConflictDetector
from src.visualization import KnowledgeGraphVisualizer

if __name__ == "__main__":
    # 1. 爬取数据
    print("开始爬取补剂数据...")
    crawler = SupplementCrawler()
    raw_data_path = crawler.crawl_all_supplements()
    print(f"数据爬取完成，保存至: {raw_data_path}")
    
    # 2. 清洗数据
    print("开始数据清洗...")
    cleaner = SupplementDataCleaner(raw_data_path)
    cleaned_data_path = cleaner.clean_data()
    print(f"数据清洗完成，保存至: {cleaned_data_path}")
    
    # 3. 构建知识图谱
    print("构建知识图谱...")
    builder = KnowledgeGraphBuilder(cleaned_data_path)
    builder.build_and_save()
    print("知识图谱构建完成")
    
    # 4. 整合中医知识
    print("整合中医知识...")
    builder.integrate_tcm_knowledge()
    print("中医知识整合完成")
    
    # 5. 执行冲突检测（示例）
    print("执行冲突检测...")
    detector = ConflictDetector(builder.graph)
    sample_supplements = ["钙", "铁"]
    conflicts = detector.detect_conflicts(sample_supplements)
    print(f"检测到 {len(conflicts)} 个冲突")
    
    # 6. 生成可视化
    print("生成知识图谱可视化...")
    visualizer = KnowledgeGraphVisualizer(builder.graph)
    visualizer.generate_all_visualizations()
    print("可视化文件已保存至images目录")
    
    print("所有流程已完成！")
