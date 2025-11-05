#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编程教学助手 - 自动化提示词优化系统
基于 PhaseEvo + Autoprompt 方法
"""

import sys
import os

# 添加必要的路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

# 插入到路径最前面，确保优先导入
sys.path.insert(0, os.path.join(parent_dir, 'EvoAutoprompt'))
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

from teaching_optimizer_wrapper import TeachingOptimizer  # 使用定制的优化器
from teaching_evaluator import TeachingPromptEvaluator, prepare_teaching_dataset
from llm import volcengine_ark_llm_eval
from datetime import datetime
import json

def main():
    print("=" * 70)
    print("编程教学助手 - 自动化提示词优化系统")
    print("基于 PhaseEvo + Autoprompt 方法")
    print("=" * 70)
    
    # 创建结果目录（在当前目录下的qwen-teaching-chatbot中）
    results_dir = os.path.join(current_dir, 'qwen-teaching-chatbot - 副本', 'results')
    os.makedirs(results_dir, exist_ok=True)
    
    # 1. 准备测试数据
    print("\n[阶段1/4] 准备测试数据集...")
    test_data = prepare_teaching_dataset()
    print(f"✓ 已准备 {len(test_data)} 个测试用例")
    
    # 统计信息
    syntax_count = sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'syntax')
    runtime_count = sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'runtime')
    logical_count = sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'logical')
    conceptual_count = sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'conceptual')
    
    beginner_count = sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'beginner')
    intermediate_count = sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'intermediate')
    advanced_count = sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'advanced')
    
    print(f"\n错误类型分布:")
    print(f"  - 语法错误 (Syntax): {syntax_count} 个")
    print(f"  - 运行时错误 (Runtime): {runtime_count} 个")
    print(f"  - 逻辑错误 (Logical): {logical_count} 个")
    print(f"  - 概念错误 (Conceptual): {conceptual_count} 个")
    
    print(f"\n难度等级分布:")
    print(f"  - 初级 (Beginner): {beginner_count} 个")
    print(f"  - 中级 (Intermediate): {intermediate_count} 个")
    print(f"  - 高级 (Advanced): {advanced_count} 个")
    
    # 2. 初始化优化器
    print("\n[阶段2/4] 初始化 PhaseEvo 优化器...")
    config = {
        'total_generations': 10,  # 总迭代次数
        'population_size': 6,      # 种群大小（增加到6个）
        'max_tokens': 999999999,   # Token预算（无限制）
        'precision_weight': 0.7,   # 偏向准确性
        'recall_weight': 0.3,
        'eval_set_size': len(test_data),
        
        # 针对教学场景的特殊配置
        'fp_pool_size': 100,       # 错误样本池大小
        'min_precision': 0.85,     # 最低准确率要求
        
        # 保守策略
        'conservative_threshold': 0.90,
        'must_include_fp': True,
        'fp_ratio': 0.6,
        
        # 并行控制（减少API并发压力）
        'max_workers': 1  # 串行评估，避免API限流
    }
    
    optimizer = TeachingOptimizer(config)  # 使用定制的教学优化器
    evaluator = TeachingPromptEvaluator(volcengine_ark_llm_eval)
    
    print("✓ 优化器初始化完成")
    print(f"\n优化配置:")
    print(f"  - 总代数: {config['total_generations']}")
    print(f"  - 种群大小: {config['population_size']}")
    print(f"  - Token预算: {config['max_tokens']:,} tokens")
    print(f"  - 准确性权重: {config['precision_weight']}")
    print(f"  - 最低准确率: {config['min_precision']}")
    
    # 3. 执行优化
    print("\n[阶段3/4] 开始自动化迭代优化...")
    print("=" * 70)
    print("预计耗时: 15-25分钟")
    print("优化过程中会显示详细进度...")
    print("=" * 70)
    
    try:
        best_candidate = optimizer.optimize(
            target_tag="编程教学错误检测",
            evaluator=evaluator,
            data=test_data
        )
    except Exception as e:
        print(f"\n❌ 优化过程出错: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 保存结果
    print("\n[阶段4/4] 保存优化结果...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 构建结果数据
    result = {
        'timestamp': timestamp,
        'method': 'PhaseEvo + Autoprompt',
        'optimized_prompt': best_candidate.prompt,
        'score': float(best_candidate.score),
        'metrics': {},
        'optimization_history': optimizer.optimization_history,
        'token_usage': {
            'consumed': optimizer.token_consumed,
            'budget': optimizer.token_budget,
            'usage_ratio': optimizer.token_consumed / optimizer.token_budget if optimizer.token_budget > 0 else 0,
            'llm_calls': optimizer.llm_call_count
        },
        'config': config,
        'test_data_info': {
            'total_samples': len(test_data),
            'syntax_errors': syntax_count,
            'runtime_errors': runtime_count,
            'logical_errors': logical_count,
            'conceptual_errors': conceptual_count,
            'beginner_level': beginner_count,
            'intermediate_level': intermediate_count,
            'advanced_level': advanced_count
        }
    }
    
    # 提取metrics（如果存在）
    if best_candidate.evidence and 'metrics' in best_candidate.evidence:
        result['metrics'] = best_candidate.evidence['metrics']
    
    # 保存完整结果（JSON）
    result_file = os.path.join(results_dir, f'optimized_prompt_{timestamp}.json')
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # 保存纯提示词文本（用于backend）
    prompt_file = os.path.join(results_dir, f'system_prompt_{timestamp}.txt')
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(best_candidate.prompt)
    
    # 保存优化历史（CSV格式，便于分析）
    if optimizer.optimization_history:
        import pandas as pd
        history_df = pd.DataFrame(optimizer.optimization_history)
        history_file = os.path.join(results_dir, f'optimization_history_{timestamp}.csv')
        history_df.to_csv(history_file, index=False, encoding='utf-8-sig')
        print(f"  - 优化历史: {history_file}")
    
    print(f"✓ 结果已保存:")
    print(f"  - 完整结果: {result_file}")
    print(f"  - 系统提示词: {prompt_file}")
    
    # 5. 输出摘要
    print("\n" + "=" * 70)
    print("优化完成摘要")
    print("=" * 70)
    print(f"\n📊 最终得分: {best_candidate.score:.4f}")
    
    if best_candidate.evidence and 'metrics' in best_candidate.evidence:
        metrics = best_candidate.evidence['metrics']
        print(f"\n详细指标:")
        print(f"  - 错误检测准确性: {metrics.get('error_detection', 0):.4f}")
        print(f"  - 教育价值: {metrics.get('educational_value', 0):.4f}")
        print(f"  - 格式规范性: {metrics.get('format_compliance', 0):.4f}")
        print(f"  - 难度适应性: {metrics.get('difficulty_adaptation', 0):.4f}")
        
        if 'stats' in metrics:
            stats = metrics['stats']
            print(f"\n分类准确率:")
            if syntax_count > 0:
                print(f"  - 语法错误: {stats.get('syntax_correct', 0)}/{syntax_count} ({stats.get('syntax_correct', 0)/syntax_count*100:.1f}%)")
            if runtime_count > 0:
                print(f"  - 运行时错误: {stats.get('runtime_correct', 0)}/{runtime_count} ({stats.get('runtime_correct', 0)/runtime_count*100:.1f}%)")
            if logical_count > 0:
                print(f"  - 逻辑错误: {stats.get('logical_correct', 0)}/{logical_count} ({stats.get('logical_correct', 0)/logical_count*100:.1f}%)")
            if conceptual_count > 0:
                print(f"  - 概念错误: {stats.get('conceptual_correct', 0)}/{conceptual_count} ({stats.get('conceptual_correct', 0)/conceptual_count*100:.1f}%)")
    
    print(f"\n💰 Token使用:")
    print(f"  - 消耗: {optimizer.token_consumed:,} / {optimizer.token_budget:,}")
    print(f"  - 使用率: {optimizer.token_consumed/optimizer.token_budget*100:.1f}%")
    print(f"  - LLM调用次数: {optimizer.llm_call_count}")
    if optimizer.llm_call_count > 0:
        print(f"  - 平均每次调用: {optimizer.token_consumed/optimizer.llm_call_count:.0f} tokens")
    
    print(f"\n🎯 优化迭代:")
    print(f"  - 总代数: {len(optimizer.optimization_history)}")
    if optimizer.optimization_history:
        best_gen = max(optimizer.optimization_history, key=lambda x: x.get('best_score', 0))
        print(f"  - 最佳代数: 第{best_gen.get('generation', 0)+1}代")
        print(f"  - 最佳得分: {best_gen.get('best_score', 0):.4f}")
    
    print("\n" + "=" * 70)
    print("✅ 优化后的提示词可直接用于 backend/server.js")
    print(f"📁 提示词文件: {prompt_file}")
    print("=" * 70)
    
    # 显示优化后的提示词预览
    print(f"\n📝 优化后的提示词预览（前300字符）:")
    print("-" * 70)
    print(best_candidate.prompt[:300] + "...")
    print("-" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断优化过程")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()

