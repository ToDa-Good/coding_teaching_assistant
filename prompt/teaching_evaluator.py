#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编程教学提示词评估器
基于错误类型分类和难度分级的评估系统
"""

import sys
import os

# 添加父目录到路径以导入llm模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm import volcengine_ark_llm_eval
import pandas as pd
import json
import re
from typing import Dict, Tuple, List, Any

class TeachingPromptEvaluator:
    """
    编程教学提示词评估器
    基于三种错误类型和三个难度等级进行评估
    """
    
    def __init__(self, llm_interface):
        self.llm_interface = llm_interface
        
        # 错误类型定义（扩展版）
        self.error_types = {
            'syntax': {
                'weight': 0.25,
                'description': '语法错误：括号、拼写、缩进、冒号等'
            },
            'runtime': {
                'weight': 0.35,
                'description': '运行时错误：除零、类型错误、键错误等'
            },
            'logical': {
                'weight': 0.25,
                'description': '逻辑错误：作用域、拷贝、迭代修改等'
            },
            'conceptual': {
                'weight': 0.15,
                'description': '概念错误：数据类型理解、算法设计等'
            }
        }
        
        # 难度等级（来自中期报告）
        self.difficulty_levels = {
            'beginner': '单点错误，易于定位',
            'intermediate': '涉及逻辑推理和跨句分析',
            'advanced': '隐藏错误，需要理解底层概念'
        }
    
    def evaluate(self, system_prompt: str, test_data: pd.DataFrame) -> Tuple[float, Dict[str, Any]]:
        """
        评估提示词在编程教学场景下的表现
        
        Args:
            system_prompt: 系统提示词
            test_data: 测试数据集
            
        Returns:
            (score, evidence): 得分和评估证据
        """
        
        total_score = 0
        perf_vector = []
        error_samples = []
        
        # 分类统计
        stats = {
            'syntax_correct': 0,
            'runtime_correct': 0,
            'logical_correct': 0,
            'conceptual_correct': 0,
            'beginner_correct': 0,
            'intermediate_correct': 0,
            'advanced_correct': 0,
            'format_correct': 0,
            'educational_value_sum': 0,
            'total': len(test_data)
        }
        
        # 按类型和难度统计
        type_counts = {'syntax': 0, 'runtime': 0, 'logical': 0, 'conceptual': 0}
        difficulty_counts = {'beginner': 0, 'intermediate': 0, 'advanced': 0}
        
        print(f"\n开始评估 {len(test_data)} 个测试样本...")
        
        for idx, row in test_data.iterrows():
            code_snippet = row['code']
            error_type = row['error_type']
            difficulty = row['difficulty']
            expected_output = row['expected_output']
            
            # 统计各类型数量
            type_counts[error_type] += 1
            difficulty_counts[difficulty] += 1
            
            # 构建完整的用户输入
            user_input = f"""请分析以下代码并找出错误：

```python
{code_snippet}
```

请按照标准格式输出：
1. 代码片段（标注错误位置）
2. 错误解释（说明错误原因和如何修正）
"""
            
            try:
                # 使用系统提示词生成回答（带重试机制）
                response = None
                max_retries = 3
                for retry in range(max_retries):
                    try:
                        response = self.llm_interface.invoke([
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_input}
                        ], thinking_mode="disabled", timeout=60)  # 禁用thinking_mode，增加超时
                        
                        if response and len(response.strip()) > 0:
                            break
                        else:
                            print(f"  样本 {idx+1}: 重试 {retry+1}/{max_retries} (空响应)")
                            import time
                            time.sleep(1)  # 等待1秒后重试
                    except Exception as e:
                        print(f"  样本 {idx+1}: 重试 {retry+1}/{max_retries} (异常: {str(e)[:50]})")
                        import time
                        time.sleep(1)
                
                if not response or len(response.strip()) == 0:
                    print(f"  样本 {idx+1}/{len(test_data)}: {error_type}/{difficulty} - LLM返回空响应（已重试{max_retries}次）")
                    perf_vector.append(0)
                    continue
                
                # 评估这个回答
                score, metrics = self._evaluate_single_response(
                    code_snippet, response, error_type, difficulty, expected_output
                )
                
                total_score += score
                perf_vector.append(1 if score >= 0.7 else 0)
                
                # 更新统计
                if score >= 0.7:
                    stats[f'{error_type}_correct'] += 1
                    stats[f'{difficulty}_correct'] += 1
                
                if metrics['format_correct']:
                    stats['format_correct'] += 1
                
                stats['educational_value_sum'] += metrics['educational_value']
                
                print(f"  样本 {idx+1}/{len(test_data)}: {error_type}/{difficulty} - 得分: {score:.3f}")
                
                # 收集错误样本（用于优化器的反馈变异）
                # 降低阈值到0.85，收集更多样本用于优化
                if score < 0.85:
                    error_samples.append({
                        'input': code_snippet,
                        'output': response,
                        'expected': expected_output,
                        'error_type': error_type,
                        'difficulty': difficulty,
                        'score': score,
                        'reason': metrics.get('failure_reason', '可以进一步优化')
                    })
                    
            except Exception as e:
                print(f"  样本 {idx+1} 评估失败: {e}")
                print(f"    错误详情: {str(e)[:200]}")
                perf_vector.append(0)
                error_samples.append({
                    'input': code_snippet,
                    'output': 'ERROR',
                    'error': str(e),
                    'error_type': error_type,
                    'difficulty': difficulty
                })
        
        # 计算各维度得分
        n = len(test_data)
        
        # 1. 错误检测准确性 (按类型加权)
        error_detection_score = 0
        for error_type, weight in [(k, v['weight']) for k, v in self.error_types.items()]:
            if type_counts[error_type] > 0:
                type_accuracy = stats[f'{error_type}_correct'] / type_counts[error_type]
                error_detection_score += type_accuracy * weight
        
        # 2. 教育价值
        educational_score = stats['educational_value_sum'] / n
        
        # 3. 格式规范性
        format_score = stats['format_correct'] / n
        
        # 4. 难度适应性
        difficulty_score = 0
        for difficulty in ['beginner', 'intermediate', 'advanced']:
            if difficulty_counts[difficulty] > 0:
                difficulty_accuracy = stats[f'{difficulty}_correct'] / difficulty_counts[difficulty]
                difficulty_score += difficulty_accuracy / 3
        
        # 综合得分（加权平均）
        final_score = (
            error_detection_score * 0.40 +
            educational_score * 0.30 +
            format_score * 0.20 +
            difficulty_score * 0.10
        )
        
        print(f"\n评估完成:")
        print(f"  错误检测: {error_detection_score:.3f}")
        print(f"  教育价值: {educational_score:.3f}")
        print(f"  格式规范: {format_score:.3f}")
        print(f"  难度适应: {difficulty_score:.3f}")
        print(f"  综合得分: {final_score:.3f}")
        
        # 构建evidence（教学任务专用）
        evidence = {
            'metrics': {
                'overall_score': final_score,
                'error_detection': error_detection_score,
                'educational_value': educational_score,
                'format_compliance': format_score,
                'difficulty_adaptation': difficulty_score,
                'error_samples': error_samples[:20],  # 保留前20个错误样本
                'stats': stats
            },
            'perf_vector': perf_vector,
            'fp_samples': error_samples,  # 低分样本，用于优化器的反馈变异
            'error_samples': error_samples  # 明确标记为错误样本
        }
        
        print(f"\n收集到 {len(error_samples)} 个待优化样本（得分<0.85）用于反馈优化")
        
        return final_score, evidence
    
    def _evaluate_single_response(self, code: str, response: str, 
                                  error_type: str, difficulty: str, 
                                  expected: str) -> Tuple[float, Dict[str, Any]]:
        """评估单个回答"""
        
        # 检查格式是否正确
        format_correct = self._check_format(response)
        
        # 使用LLM评估教育价值和准确性
        eval_prompt = f"""请评估以下编程教学助手的回答质量：

【学生代码】
```python
{code}
```

【错误类型】{error_type}
【难度等级】{difficulty}

【助手回答】
{response}

【期望输出要点】
{expected}

请评估以下方面（每项0-1分）：
1. 错误识别准确性：是否正确识别了错误位置和类型
2. 教育引导性：是否引导学生思考而非直接给答案，是否提供了学习建议
3. 解释清晰度：解释是否清晰易懂，是否包含了修正方法

返回JSON格式（不要其他内容）：
{{
    "accuracy": 0.8,
    "guidance": 0.7,
    "clarity": 0.9,
    "failure_reason": "如果有问题，说明原因"
}}"""

        try:
            eval_result = self.llm_interface.invoke([
                {"role": "user", "content": eval_prompt}
            ], thinking_mode="disabled")
            
            if not eval_result:
                print(f"    评估LLM返回空响应")
                return 0.5, {
                    'format_correct': format_correct,
                    'educational_value': 0.5,
                    'failure_reason': 'LLM返回空'
                }
            
            # 解析JSON
            json_match = re.search(r'\{[^}]+\}', eval_result, re.DOTALL)
            if json_match:
                try:
                    metrics = json.loads(json_match.group())
                except json.JSONDecodeError as e:
                    print(f"    JSON解析失败: {e}")
                    print(f"    原始响应: {eval_result[:200]}")
                    # 尝试手动提取
                    metrics = self._extract_metrics_manually(eval_result)
            else:
                # 尝试提取数字
                print(f"    未找到JSON格式，尝试手动提取")
                metrics = self._extract_metrics_manually(eval_result)
            
            # 计算综合分数
            score = (
                metrics.get('accuracy', 0.5) * 0.5 +
                metrics.get('guidance', 0.5) * 0.3 +
                metrics.get('clarity', 0.5) * 0.2
            )
            
            return score, {
                'format_correct': format_correct,
                'educational_value': metrics.get('guidance', 0.5),
                'failure_reason': metrics.get('failure_reason', '')
            }
            
        except Exception as e:
            print(f"    单样本评估失败: {e}")
            import traceback
            traceback.print_exc()
            return 0.5, {
                'format_correct': format_correct,
                'educational_value': 0.5,
                'failure_reason': str(e)
            }
    
    def _extract_metrics_manually(self, text: str) -> dict:
        """手动从文本中提取评分"""
        accuracy_match = re.search(r'accuracy["\s:]+(\d+\.?\d*)', text, re.IGNORECASE)
        guidance_match = re.search(r'guidance["\s:]+(\d+\.?\d*)', text, re.IGNORECASE)
        clarity_match = re.search(r'clarity["\s:]+(\d+\.?\d*)', text, re.IGNORECASE)
        
        return {
            'accuracy': float(accuracy_match.group(1)) if accuracy_match else 0.5,
            'guidance': float(guidance_match.group(1)) if guidance_match else 0.5,
            'clarity': float(clarity_match.group(1)) if clarity_match else 0.5
        }
    
    def _check_format(self, response: str) -> bool:
        """检查输出格式是否符合标准化要求"""
        # 检查是否包含代码片段
        has_code = '```' in response or 'def ' in response or 'return' in response
        
        # 检查是否包含错误解释
        has_explanation = '错误' in response or 'Error' in response or '问题' in response or '修正' in response
        
        return has_code and has_explanation


def load_error_database(csv_paths: list = None) -> pd.DataFrame:
    """
    从多个CSV文件加载错误数据库并合并
    """
    if csv_paths is None:
        base_dir = os.path.dirname(__file__)
        csv_paths = [
            os.path.join(base_dir, '语法错误数据库_扩充版.csv'),
            os.path.join(base_dir, '内容错误数据库_完整版200条.csv'),
            os.path.join(base_dir, '逻辑错误数据库_完整版200条.csv')
        ]
    
    all_dataframes = []
    total_records = 0
    
    for csv_path in csv_paths:
        try:
            df = pd.read_csv(csv_path, encoding='utf-8')
            all_dataframes.append(df)
            total_records += len(df)
            filename = os.path.basename(csv_path)
            print(f"  ✓ {filename}: {len(df)} 条")
        except FileNotFoundError:
            print(f"  ⚠️  未找到: {os.path.basename(csv_path)}")
        except Exception as e:
            print(f"  ❌ 加载失败 {os.path.basename(csv_path)}: {e}")
    
    if not all_dataframes:
        print(f"❌ 未能加载任何错误数据库")
        return None
    
    # 合并所有数据框
    combined_df = pd.concat(all_dataframes, ignore_index=True)
    print(f"✓ 总计: {total_records} 条记录")
    
    return combined_df

def prepare_teaching_dataset() -> pd.DataFrame:
    """
    准备测试数据集
    基于错误数据库CSV文件生成测试用例
    """
    # 加载错误数据库
    error_db = load_error_database()
    
    if error_db is None or len(error_db) == 0:
        print("⚠️ 错误数据库为空，使用默认测试用例")
        return prepare_default_dataset()
    
    test_cases = []
    
    # 从错误数据库中采样生成测试用例
    for _, row in error_db.iterrows():
        error_type_cn = row['错误类型']  # 中文错误类型
        difficulty_cn = row['错误等级']  # 中文难度
        explanation = row['错误解释']
        
        # 错误描述（语法错误有，内容/逻辑错误没有）
        description = row.get('错误描述', explanation)
        
        # 映射中文到英文（扩展映射）
        error_type_map = {
            # 语法错误
            '缩进错误': 'syntax',
            '冒号遗漏': 'syntax',
            '括号不匹配': 'syntax',
            '引号错误': 'syntax',
            # 内容错误
            '除零错误': 'runtime',
            '编码问题': 'runtime',
            '键错误': 'runtime',
            '值错误': 'runtime',
            '类型错误': 'runtime',
            '文件未关闭': 'runtime',
            '循环导入': 'runtime',
            # 逻辑错误
            '变量作用域误解': 'logical',
            '浅拷贝与深拷贝': 'logical',
            '迭代中修改集合': 'logical',
            '可变默认参数': 'logical',
            '浮点数精度问题': 'logical',
            '循环引用内存泄漏': 'logical',
            '类型比较错误': 'logical',
            '逻辑错误': 'logical',
            '概念错误': 'conceptual'
        }
        
        difficulty_map = {
            '初级': 'beginner',
            '中级': 'intermediate',
            '高级': 'advanced'
        }
        
        error_type = error_type_map.get(error_type_cn, 'runtime')
        difficulty = difficulty_map.get(difficulty_cn, 'beginner')
        
        # 根据错误描述生成代码示例
        code_example = generate_code_example(error_type_cn, description, difficulty)
        
        test_cases.append({
            'code': code_example,
            'error_type': error_type,
            'difficulty': difficulty,
            'expected_output': f"{error_type_cn}：{description}"
        })
    
    # 限制测试集大小（避免太大）
    # 按照错误类型和难度均匀采样
    sampled_cases = sample_balanced_cases(test_cases, max_samples=30)
    
    print(f"✓ 生成测试数据集: {len(sampled_cases)} 个样本")
    return pd.DataFrame(sampled_cases)

def generate_code_example(error_type: str, description: str, difficulty: str) -> str:
    """
    根据错误类型和描述生成代码示例
    """
    # ========== 语法错误 ==========
    if '缩进' in error_type:
        if '函数内无缩进' in description:
            return '''def hello():
print("Hello")  # 缺少缩进'''
        elif 'if语句内无缩进' in description:
            return '''if x > 0:
print(x)  # 缺少缩进'''
        elif 'for循环内无缩进' in description:
            return '''for i in range(5):
print(i)  # 缺少缩进'''
        elif '混合使用空格和制表符' in description:
            return '''def test():
    print("line1")  # 4个空格
\tprint("line2")  # 1个制表符'''
        else:
            return '''def example():
print("indentation error")  # 缺少缩进'''
    
    elif '冒号' in error_type:
        if 'if语句' in description:
            return '''if x > 0  # 缺少冒号
    print(x)'''
        elif 'for循环' in description:
            return '''for i in range(5)  # 缺少冒号
    print(i)'''
        elif '函数定义' in description:
            return '''def hello()  # 缺少冒号
    print("Hello")'''
        else:
            return '''if condition  # 缺少冒号
    do_something()'''
    
    # ========== 内容错误（运行时错误）==========
    elif '除零' in error_type:
        return '''def calculate(a, b):
    return a / b  # 当b=0时会报错

result = calculate(10, 0)'''
    
    elif '类型错误' in error_type:
        return '''x = "10"
y = 5
result = x + y  # 字符串和整数不能相加'''
    
    elif '键错误' in error_type:
        return '''data = {'name': 'Alice', 'age': 25}
print(data['address'])  # 键不存在'''
    
    elif '值错误' in error_type:
        return '''num = int("abc")  # 无法将非数字字符串转换为整数'''
    
    elif '编码' in error_type:
        return '''with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()  # 文件实际是GBK编码'''
    
    elif '循环导入' in error_type:
        return '''# module_a.py
from module_b import func_b

# module_b.py
from module_a import func_a  # 循环导入'''
    
    elif '文件未关闭' in error_type:
        return '''f = open('data.txt', 'r')
data = f.read()
# 忘记关闭文件'''
    
    # ========== 逻辑错误 ==========
    elif '作用域' in error_type:
        return '''def func():
    x = 10
    def inner():
        x = x + 1  # UnboundLocalError
    inner()'''
    
    elif '拷贝' in error_type:
        return '''original = [1, 2, [3, 4]]
copy = original.copy()  # 浅拷贝
copy[2][0] = 99  # 修改了原列表'''
    
    elif '可变默认参数' in error_type:
        return '''def append_to(element, target=[]):
    target.append(element)
    return target

list1 = append_to(1)  # [1]
list2 = append_to(2)  # [1, 2] 而不是 [2]'''
    
    elif '迭代中修改' in error_type:
        return '''items = [1, 2, 3, 4, 5]
for item in items:
    if item % 2 == 0:
        items.remove(item)  # 迭代中修改列表'''
    
    elif '浮点数精度' in error_type:
        return '''a = 0.1 + 0.2
if a == 0.3:  # False，因为浮点数精度问题
    print("Equal")'''
    
    elif '循环引用' in error_type:
        return '''class Node:
    def __init__(self):
        self.ref = None

a = Node()
b = Node()
a.ref = b
b.ref = a  # 循环引用'''
    
    elif '类型比较' in error_type:
        return '''x = [1, 2, 3]
y = [1, 2, 3]
if x is y:  # False，应该用 ==
    print("Same")'''
    
    # 默认示例
    return f'''# {description}
def example():
    # 这里有一个 {error_type} 错误
    pass'''

def sample_balanced_cases(cases: list, max_samples: int = 20, seed: int = 42) -> list:
    """
    均衡采样测试用例
    确保各种错误类型和难度都有覆盖
    
    Args:
        cases: 测试用例列表
        max_samples: 最大样本数
        seed: 随机种子（固定种子确保每次采样结果一致）
    """
    import random
    
    # 设置固定随机种子，确保每次采样结果一致
    random.seed(seed)
    
    # 按错误类型和难度分组
    groups = {}
    for case in cases:
        key = (case['error_type'], case['difficulty'])
        if key not in groups:
            groups[key] = []
        groups[key].append(case)
    
    # 从每组中采样
    sampled = []
    samples_per_group = max(1, max_samples // len(groups))
    
    for key, group_cases in sorted(groups.items()):  # 排序确保顺序一致
        sample_count = min(samples_per_group, len(group_cases))
        sampled.extend(random.sample(group_cases, sample_count))
    
    # 如果还不够，随机补充
    if len(sampled) < max_samples:
        remaining = [c for c in cases if c not in sampled]
        if remaining:
            additional = min(max_samples - len(sampled), len(remaining))
            sampled.extend(random.sample(remaining, additional))
    
    return sampled[:max_samples]

def prepare_default_dataset() -> pd.DataFrame:
    """
    默认测试数据集（备用）
    """
    test_cases = [
        # ========== 语法错误 (Syntax Errors) ==========
        
        # Beginner - 单点错误
        {
            'code': '''def factorial(n):
    if n == 0:
        return 0  # Error: Should return 1
    else:
        return n * factorial(n-1)''',
            'error_type': 'logical',  # 修正：这是逻辑错误，不是语法错误
            'difficulty': 'beginner',
            'expected_output': '基础情况错误：n=0时应返回1，否则所有结果都为0'
        },
        
        {
            'code': '''def print_numbers(n):
    for i in range(n)
        print(i)  # Missing colon after for statement''',
            'error_type': 'syntax',
            'difficulty': 'beginner',
            'expected_output': 'for语句后缺少冒号'
        },
        
        # Intermediate - 需要分析
        {
            'code': '''def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)  # Error: Division by zero if empty''',
            'error_type': 'logical',  # 修正：这是逻辑错误（缺少边界检查）
            'difficulty': 'intermediate',
            'expected_output': '空列表会导致除零错误，需要添加检查'
        },
        
        # ========== 逻辑错误 (Logical Errors) ==========
        
        # Beginner
        {
            'code': '''def is_even(n):
    if n % 2 == 1:
        return True  # Error: Logic reversed
    return False''',
            'error_type': 'logical',
            'difficulty': 'beginner',
            'expected_output': '逻辑反转：n%2==1时应返回False'
        },
        
        # Intermediate - 需要跨句分析
        {
            'code': '''def swap(arr, i, j):
    temp = arr[i]
    arr[i] = arr[j]
    # Missing: arr[j] = temp
    return arr''',
            'error_type': 'logical',
            'difficulty': 'intermediate',
            'expected_output': '交换逻辑不完整：缺少arr[j]=temp，导致值丢失'
        },
        
        {
            'code': '''def find_max(numbers):
    max_num = 0  # Error: Fails for all negative numbers
    for num in numbers:
        if num > max_num:
            max_num = num
    return max_num''',
            'error_type': 'logical',
            'difficulty': 'intermediate',
            'expected_output': '初始化错误：max_num=0无法处理全负数列表'
        },
        
        # Advanced - 需要理解底层概念
        {
            'code': '''def remove_duplicates(lst):
    for item in lst:
        if lst.count(item) > 1:
            lst.remove(item)  # Error: Modifying list while iterating
    return lst''',
            'error_type': 'logical',
            'difficulty': 'advanced',
            'expected_output': '迭代时修改列表会导致跳过元素和索引错误'
        },
        
        # ========== 概念错误 (Conceptual Errors) ==========
        
        # Beginner
        {
            'code': '''def add_to_list(item, my_list=[]):
    my_list.append(item)  # Error: Mutable default argument
    return my_list''',
            'error_type': 'conceptual',
            'difficulty': 'beginner',
            'expected_output': '可变默认参数陷阱：列表会在多次调用间共享'
        },
        
        # Intermediate
        {
            'code': '''def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-1)  # Error: Should be n-2''',
            'error_type': 'conceptual',
            'difficulty': 'intermediate',
            'expected_output': '递归逻辑错误：第二项应该是fibonacci(n-2)'
        },
        
        # Advanced - 需要深入理解
        {
            'code': '''def recursive_sum(n):
    if n == 1:
        return 1
    return n + recursive_sum(n)  # Error: Should be n-1, causes infinite recursion''',
            'error_type': 'conceptual',
            'difficulty': 'advanced',
            'expected_output': '无限递归：递归调用应该是n-1，否则永不终止'
        },
        
        {
            'code': '''class Counter:
    count = 0  # Error: Class variable, not instance variable
    
    def increment(self):
        self.count += 1
        
c1 = Counter()
c2 = Counter()
c1.increment()  # Both c1 and c2 affected''',
            'error_type': 'conceptual',
            'difficulty': 'advanced',
            'expected_output': '类变量与实例变量混淆：count是类变量，所有实例共享'
        },
        
        # ========== 混合场景 ==========
        
        {
            'code': '''def binary_search(arr, target):
    left, right = 0, len(arr)  # Error: Should be len(arr)-1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1''',
            'error_type': 'logical',
            'difficulty': 'intermediate',
            'expected_output': '边界错误：right应初始化为len(arr)-1，否则索引越界'
        },
        
        {
            'code': '''def merge_sorted_lists(list1, list2):
    result = []
    i = j = 0
    while i < len(list1) and j < len(list2):
        if list1[i] < list2[j]:
            result.append(list1[i])
            i += 1
        else:
            result.append(list2[j])
            j += 1
    # Missing: Append remaining elements
    return result''',
            'error_type': 'logical',
            'difficulty': 'intermediate',
            'expected_output': '逻辑不完整：未处理剩余元素，应添加result.extend(list1[i:])和result.extend(list2[j:])'
        }
    ]
    
    return pd.DataFrame(test_cases)


if __name__ == "__main__":
    # 测试评估器
    print("测试编程教学评估器...")
    
    evaluator = TeachingPromptEvaluator(volcengine_ark_llm_eval)
    test_data = prepare_teaching_dataset()
    
    print(f"\n准备了 {len(test_data)} 个测试用例:")
    print(f"  语法错误: {sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'syntax')}")
    print(f"  逻辑错误: {sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'logical')}")
    print(f"  概念错误: {sum(1 for _, r in test_data.iterrows() if r['error_type'] == 'conceptual')}")
    print(f"  初级: {sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'beginner')}")
    print(f"  中级: {sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'intermediate')}")
    print(f"  高级: {sum(1 for _, r in test_data.iterrows() if r['difficulty'] == 'advanced')}")
    
    # 测试一个简单的提示词
    test_prompt = """你是一个编程教学助手。当学生提交代码时，你需要：
1. 仔细分析代码，找出错误
2. 用清晰的语言解释错误原因
3. 引导学生思考如何修正，而不是直接给出答案
4. 提供学习建议

输出格式：
- 代码片段（标注错误位置）
- 错误解释
- 修正建议"""
    
    print("\n测试评估...")
    score, evidence = evaluator.evaluate(test_prompt, test_data.head(3))
    
    print(f"\n测试完成！得分: {score:.3f}")

