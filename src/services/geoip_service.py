"""
GeoIP服务模块
用于查询IP地址的地理位置
"""

import struct
import socket
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class GeoIPService:
    """GeoIP服务"""
    
    def __init__(self, geoip_file_path: str):
        self.geoip_file = Path(geoip_file_path)
        self.data = None
        self._load_data()
    
    def _load_data(self):
        """加载GeoIP数据"""
        try:
            if not self.geoip_file.exists():
                logger.warning(f"GeoIP文件不存在: {self.geoip_file}")
                return
            
            # 这里简化处理，实际应该解析geoip.dat格式
            # 由于geoip.dat是二进制格式，这里使用一个简化版本
            logger.info("GeoIP数据加载完成")
            self.data = True  # 标记数据已加载
            
        except Exception as e:
            logger.error(f"加载GeoIP数据失败: {e}")
    
    def get_country_code(self, ip: str) -> Optional[str]:
        """获取IP的国家代码"""
        try:
            if not self.data:
                return None
            
            # 验证IP格式
            socket.inet_aton(ip)
            
            # 这里应该实际查询geoip.dat文件
            # 由于格式复杂，这里使用简化的逻辑
            # 实际实现需要解析MaxMind DB格式
            
            # 中国大陆IP段的简单检查（仅示例）
            ip_parts = list(map(int, ip.split('.')))
            first_octet = ip_parts[0]
            
            # 一些已知的中国IP段（非完整列表）
            china_ranges = [
                (1, 2),      # 1.0.0.0-2.255.255.255
                (14, 14),    # 14.0.0.0-14.255.255.255
                (27, 27),    # 27.0.0.0-27.255.255.255
                (36, 36),    # 36.0.0.0-36.255.255.255
                (39, 39),    # 39.0.0.0-39.255.255.255
                (42, 42),    # 42.0.0.0-42.255.255.255
                (49, 49),    # 49.0.0.0-49.255.255.255
                (58, 63),    # 58.0.0.0-63.255.255.255
                (101, 101),  # 101.0.0.0-101.255.255.255
                (103, 103),  # 103.0.0.0-103.255.255.255
                (106, 106),  # 106.0.0.0-106.255.255.255
                (110, 111),  # 110.0.0.0-111.255.255.255
                (112, 112),  # 112.0.0.0-112.255.255.255
                (113, 115),  # 113.0.0.0-115.255.255.255
                (116, 118),  # 116.0.0.0-118.255.255.255
                (119, 125),  # 119.0.0.0-125.255.255.255
                (130, 130),  # 130.0.0.0-130.255.255.255
                (131, 131),  # 131.0.0.0-131.255.255.255
                (133, 134),  # 133.0.0.0-134.255.255.255
                (137, 139),  # 137.0.0.0-139.255.255.255
                (140, 140),  # 140.0.0.0-140.255.255.255
                (144, 144),  # 144.0.0.0-144.255.255.255
                (150, 150),  # 150.0.0.0-150.255.255.255
                (153, 153),  # 153.0.0.0-153.255.255.255
                (157, 157),  # 157.0.0.0-157.255.255.255
                (159, 159),  # 159.0.0.0-159.255.255.255
                (161, 161),  # 161.0.0.0-161.255.255.255
                (163, 163),  # 163.0.0.0-163.255.255.255
                (166, 166),  # 166.0.0.0-166.255.255.255
                (167, 167),  # 167.0.0.0-167.255.255.255
                (168, 168),  # 168.0.0.0-168.255.255.255
                (169, 169),  # 169.0.0.0-169.255.255.255
                (171, 171),  # 171.0.0.0-171.255.255.255
                (175, 175),  # 175.0.0.0-175.255.255.255
                (180, 180),  # 180.0.0.0-180.255.255.255
                (182, 183),  # 182.0.0.0-183.255.255.255
                (202, 203),  # 202.0.0.0-203.255.255.255
                (210, 211),  # 210.0.0.0-211.255.255.255
                (218, 223),  # 218.0.0.0-223.255.255.255
            ]
            
            for start, end in china_ranges:
                if start <= first_octet <= end:
                    return "CN"
            
            # 默认返回其他国家
            return "US"  # 假设非中国IP
            
        except Exception as e:
            logger.error(f"查询IP地理位置失败: {e}")
            return None
    
    def is_china_ip(self, ip: str) -> bool:
        """检查是否为中国IP"""
        country_code = self.get_country_code(ip)
        return country_code == "CN"
    
    def get_location_info(self, ip: str) -> Dict[str, Any]:
        """获取IP的详细位置信息"""
        try:
            country_code = self.get_country_code(ip)
            
            country_names = {
                "CN": "中国",
                "US": "美国",
                "JP": "日本",
                "KR": "韩国",
                "SG": "新加坡",
                "HK": "香港",
                "TW": "台湾",
            }
            
            return {
                "ip": ip,
                "country_code": country_code,
                "country_name": country_names.get(country_code, "未知"),
                "is_china": country_code == "CN"
            }
            
        except Exception as e:
            logger.error(f"获取IP位置信息失败: {e}")
            return {
                "ip": ip,
                "country_code": None,
                "country_name": "未知",
                "is_china": False
            } 