"""DeepSeek AI引擎 - 客服回复生成"""
import json
import requests
import time


class AIEngine:
    """调用DeepSeek API生成客服推荐回复"""

    API_URL = "https://api.deepseek.com/v1/chat/completions"
    MODEL = "deepseek-chat"  # V3, 不思考模式

    SYSTEM_PROMPT = """你是电商客服回复助手。根据客户消息生成简洁专业的回复。
规则:
1. 语气友好专业，可使用"亲"等电商用语
2. 直接回答问题，不超过3句话
3. 如涉及优惠/活动，可引用店铺当前活动信息
4. 不确定的信息建议客户查看详情页或留言后续跟进
5. 只输出回复内容，不要任何解释、前缀或标记"""

    def __init__(self, api_key=None):
        self.api_key = api_key
        self.last_response = ""
        self.last_error = ""
        self.timeout = 30  # API超时秒数

    def set_api_key(self, api_key):
        """设置API密钥"""
        self.api_key = api_key

    def generate_reply(self, customer_msg, context_phrases=None):
        """
        根据客户消息生成推荐回复
        
        Args:
            customer_msg: 客户最近的消息文本
            context_phrases: 相关话术列表（可选，用于参考）
            
        Returns:
            dict: {
                "success": bool,
                "reply": str,     # 生成的回复
                "error": str      # 错误信息
            }
        """
        if not self.api_key:
            return {"success": False, "reply": "", "error": "未设置API Key"}

        if not customer_msg:
            return {"success": False, "reply": "", "error": "客户消息为空"}

        # 构造用户消息
        user_content = f"客户消息：{customer_msg}"
        if context_phrases:
            user_content += f"\n\n店铺话术参考：\n{context_phrases}"

        # 构造请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7,
            "max_tokens": 200,
            "stream": False
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                reply = data["choices"][0]["message"]["content"].strip()
                self.last_response = reply
                return {"success": True, "reply": reply, "error": ""}
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', '')}"
                except:
                    error_msg += f" - {response.text[:100]}"
                self.last_error = error_msg
                return {"success": False, "reply": "", "error": error_msg}

        except requests.exceptions.Timeout:
            return {"success": False, "reply": "", "error": "API请求超时，请检查网络"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "reply": "", "error": "网络连接失败，请检查网络"}
        except Exception as e:
            return {"success": False, "reply": "", "error": f"未知错误: {str(e)}"}

    def generate_with_retry(self, customer_msg, context_phrases=None, max_retries=2):
        """带重试的生成回复"""
        for i in range(max_retries + 1):
            result = self.generate_reply(customer_msg, context_phrases)
            if result["success"]:
                return result
            if i < max_retries and "超时" in result["error"]:
                time.sleep(1)
                continue
            return result
        return result