"""
使用大模型生成初始种子提示词
"""
import sys
import os

# 添加父目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
sys.path.insert(0, current_dir)

from llm import volcengine_ark_llm_eval
import json

def generate_seed_prompts(num_seeds: int = 6) -> list:
    """
    使用大模型生成多样化的初始种子提示词
    
    Args:
        num_seeds: 需要生成的种子数量
        
    Returns:
        list: 生成的提示词列表
    """
    llm = volcengine_ark_llm_eval
    
    generation_prompt = f"""你是一位提示词工程专家，专门为编程教学助手设计高质量的系统提示词。

【任务】
请生成 {num_seeds} 个不同风格的Python编程教学助手系统提示词。这些提示词将用于优化算法的初始种群。

【要求】
1. **多样性**：每个提示词应该有不同的教学风格和侧重点
2. **自然语言**：使用自然语言描述，不要求JSON格式输出
3. **教学导向**：强调引导学生思考，而非直接给答案
4. **全面覆盖**：能处理语法错误、运行时错误、逻辑错误
5. **清晰结构**：每个提示词应该有清晰的教学流程

【错误类型覆盖】
- 语法错误：缩进、冒号、括号、引号
- 运行时错误：除零、类型错误、键错误、值错误、文件错误
- 逻辑错误：作用域、拷贝、迭代修改、可变默认参数、浮点精度

【教学风格建议】
1. 友好引导型：耐心、鼓励式
2. 结构化教学型：步骤清晰、系统性强
3. 实践导向型：强调动手实践
4. 简洁清晰型：直接明了
5. 对话式教学型：亲切对话
6. 分层教学型：根据难度分层

【输出格式】
请以JSON数组格式输出，每个提示词作为一个字符串：
```json
[
  "第1个提示词内容...",
  "第2个提示词内容...",
  ...
]
```

【注意】
- 每个提示词长度适中（200-400字）
- 避免过度严格的规则
- 强调教育价值和引导性
- 输出格式要求学生友好（不强制JSON）

请生成 {num_seeds} 个高质量的种子提示词："""

    print("🤖 正在使用大模型生成初始种子提示词...")
    print(f"   目标数量: {num_seeds} 个")
    
    try:
        response = llm.invoke([
            {"role": "user", "content": generation_prompt}
        ], thinking_mode="disabled", timeout=120)
        
        if not response:
            print("❌ 大模型返回空响应")
            return []
        
        # 提取JSON数组
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                prompts = json.loads(json_match.group())
                print(f"✅ 成功生成 {len(prompts)} 个种子提示词")
                
                # 显示预览
                for i, prompt in enumerate(prompts, 1):
                    preview = prompt[:80].replace('\n', ' ')
                    print(f"   [{i}] {preview}...")
                
                return prompts
            except json.JSONDecodeError as e:
                print(f"❌ JSON解析失败: {e}")
                print(f"   原始响应: {response[:200]}...")
                return []
        else:
            print("❌ 未找到JSON格式")
            print(f"   原始响应: {response[:200]}...")
            return []
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def save_seed_prompts(prompts: list, output_file: str = "generated_seed_prompts.json"):
    """
    保存生成的种子提示词到文件
    """
    output_path = os.path.join(os.path.dirname(__file__), output_file)
    
    data = {
        "timestamp": __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S"),
        "num_prompts": len(prompts),
        "prompts": prompts
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到: {output_path}")
    return output_path


def main():
    """主函数"""
    print("=" * 70)
    print("🌟 大模型生成初始种子提示词")
    print("=" * 70)
    
    # 生成种子提示词
    prompts = generate_seed_prompts(num_seeds=6)
    
    if prompts:
        # 保存到文件
        output_file = save_seed_prompts(prompts)
        
        print("\n" + "=" * 70)
        print("✅ 生成完成！")
        print("=" * 70)
        print(f"\n下一步：")
        print(f"1. 查看生成的提示词: {output_file}")
        print(f"2. 如果满意，运行优化: python optimize_teaching_prompt.py")
        print(f"3. 优化器会自动加载这些种子提示词")
    else:
        print("\n" + "=" * 70)
        print("❌ 生成失败，将使用默认种子提示词")
        print("=" * 70)


if __name__ == "__main__":
    main()

