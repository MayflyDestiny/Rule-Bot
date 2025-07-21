"""
DNS服务模块
使用DoH (DNS over HTTPS) 查询域名解析
"""

import aiohttp
import asyncio
import base64
import struct
import socket
from typing import List, Optional, Dict, Any
from loguru import logger


class DNSService:
    """DNS服务"""
    
    def __init__(self, doh_servers: Dict[str, str], ns_doh_servers: Dict[str, str] = None):
        self.doh_servers = doh_servers
        self.ns_doh_servers = ns_doh_servers or doh_servers
    
    async def query_a_record(self, domain: str, use_edns_china: bool = True) -> List[str]:
        """查询A记录，返回IP地址列表"""
        try:
            # 构建DNS查询数据包
            query_data = self._build_dns_query(domain, use_edns_china)
            
            # 尝试多个DoH服务器
            for server_name, server_url in self.doh_servers.items():
                try:
                    ips = await self._query_doh_server(server_url, query_data)
                    if ips:
                        logger.debug(f"使用 {server_name} 查询 {domain} 成功，获得 {len(ips)} 个IP")
                        return ips
                except Exception as e:
                    logger.warning(f"DoH服务器 {server_name} 查询失败: {e}")
                    continue
            
            logger.warning(f"所有DoH服务器查询域名 {domain} 都失败")
            return []
            
        except Exception as e:
            logger.error(f"DNS查询失败: {e}")
            return []
    
    async def query_ns_records(self, domain: str) -> List[str]:
        """查询NS记录，返回权威域名服务器列表"""
        try:
            # 构建NS查询数据包（不使用EDNS中国客户端，避免被过滤）
            query_data = self._build_dns_query(domain, False, record_type=2)  # NS记录类型为2
            
            # 使用专门的国际DoH服务器查询NS记录
            for server_name, server_url in self.ns_doh_servers.items():
                try:
                    ns_servers = await self._query_doh_server_ns(server_url, query_data)
                    if ns_servers:
                        logger.debug(f"使用国际DoH {server_name} 查询 {domain} NS记录成功")
                        return ns_servers
                except Exception as e:
                    logger.warning(f"国际DoH服务器 {server_name} NS查询失败: {e}")
                    continue
            
            # DoH查询失败时，尝试使用系统DNS作为备用
            logger.info(f"DoH查询NS记录失败，尝试使用系统DNS查询 {domain}")
            ns_servers = await self._query_ns_system_dns(domain)
            if ns_servers:
                logger.debug(f"使用系统DNS查询 {domain} NS记录成功")
                return ns_servers
            
            logger.warning(f"所有NS记录查询方法都失败，域名: {domain}")
            return []
            
        except Exception as e:
            logger.error(f"NS记录查询失败: {e}")
            return []
    
    async def _query_ns_system_dns(self, domain: str) -> List[str]:
        """使用系统DNS查询NS记录作为备用方案"""
        try:
            import dns.resolver
            import dns.rdatatype
            
            # 创建解析器
            resolver = dns.resolver.Resolver()
            resolver.timeout = 10
            resolver.lifetime = 10
            
            # 查询NS记录
            answers = resolver.resolve(domain, dns.rdatatype.NS)
            ns_servers = [str(rdata).rstrip('.') for rdata in answers]
            
            logger.debug(f"系统DNS查询 {domain} NS记录成功，获得 {len(ns_servers)} 个NS服务器")
            return ns_servers
            
        except ImportError:
            logger.warning("dnspython库未安装，无法使用系统DNS备用查询")
            return []
        except Exception as e:
            logger.warning(f"系统DNS查询NS记录失败: {e}")
            return []
    
    def _build_dns_query(self, domain: str, use_edns_china: bool = True, record_type: int = 1) -> bytes:
        """构建DNS查询数据包"""
        try:
            # DNS头部 (12字节)
            transaction_id = 0x1234
            flags = 0x0100  # 标准查询
            questions = 1
            answer_rrs = 0
            authority_rrs = 0
            additional_rrs = 1 if use_edns_china else 0
            
            header = struct.pack('!HHHHHH', 
                               transaction_id, flags, questions, 
                               answer_rrs, authority_rrs, additional_rrs)
            
            # 构建查询部分
            query = b''
            for label in domain.split('.'):
                query += struct.pack('!B', len(label)) + label.encode('ascii')
            query += b'\x00'  # 结束标志
            
            query += struct.pack('!HH', record_type, 1)  # Type A/NS, Class IN
            
            # 如果使用EDNS，添加OPT记录以模拟中国境内查询
            edns = b''
            if use_edns_china:
                # OPT记录格式
                edns += b'\x00'  # Name (root)
                edns += struct.pack('!H', 41)  # Type OPT
                edns += struct.pack('!H', 4096)  # UDP payload size
                edns += struct.pack('!H', 0)  # Extended RCODE and flags
                edns += struct.pack('!H', 8)  # RDLEN (8 bytes for ECS)
                
                # ECS (EDNS Client Subnet) 选项
                edns += struct.pack('!H', 8)  # Option code (ECS)
                edns += struct.pack('!H', 4)  # Option length
                edns += struct.pack('!H', 1)  # Family (IPv4)
                edns += struct.pack('!BB', 24, 0)  # Source netmask, Scope netmask
                # 使用中国的IP段 (例如: 219.0.0.0/24)
                edns += struct.pack('!BBB', 219, 0, 0)
            
            return header + query + edns
            
        except Exception as e:
            logger.error(f"构建DNS查询包失败: {e}")
            return b''
    
    async def _query_doh_server(self, server_url: str, query_data: bytes) -> List[str]:
        """查询DoH服务器并解析A记录"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                encoded_query = base64.urlsafe_b64encode(query_data).decode().rstrip('=')
                url = f"{server_url}?dns={encoded_query}"
                
                connector = aiohttp.TCPConnector(
                    limit=10,
                    limit_per_host=5,
                    ttl_dns_cache=300,
                    use_dns_cache=True
                )
                
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(
                        url,
                        headers={
                            'Accept': 'application/dns-message',
                            'User-Agent': 'Rule-Bot DNS Client/1.0'
                        },
                        timeout=aiohttp.ClientTimeout(total=15, connect=5)
                    ) as response:
                        if response.status == 200:
                            response_data = await response.read()
                            result = self._parse_dns_response_a(response_data)
                            if result:  # 只有获得结果才返回
                                return result
                            elif attempt < max_retries - 1:
                                logger.debug(f"DoH A查询无结果，重试第 {attempt + 2} 次")
                                await asyncio.sleep(1)
                                continue
                        else:
                            raise Exception(f"HTTP错误: {response.status}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"DoH A查询超时，尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
            except Exception as e:
                logger.error(f"DoH A查询失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
        
        return []
    
    async def _query_doh_server_ns(self, server_url: str, query_data: bytes) -> List[str]:
        """查询DoH服务器并解析NS记录"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                encoded_query = base64.urlsafe_b64encode(query_data).decode().rstrip('=')
                url = f"{server_url}?dns={encoded_query}"
                
                connector = aiohttp.TCPConnector(
                    limit=10,
                    limit_per_host=5,
                    ttl_dns_cache=300,
                    use_dns_cache=True
                )
                
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(
                        url,
                        headers={
                            'Accept': 'application/dns-message',
                            'User-Agent': 'Rule-Bot DNS Client/1.0'
                        },
                        timeout=aiohttp.ClientTimeout(total=15, connect=5)
                    ) as response:
                        if response.status == 200:
                            response_data = await response.read()
                            result = self._parse_dns_response_ns(response_data)
                            if result:  # 只有获得结果才返回
                                return result
                            elif attempt < max_retries - 1:
                                logger.debug(f"DoH NS查询无结果，重试第 {attempt + 2} 次")
                                await asyncio.sleep(1)
                                continue
                        else:
                            raise Exception(f"HTTP错误: {response.status}")
                            
            except asyncio.TimeoutError:
                logger.warning(f"DoH NS查询超时，尝试 {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
            except Exception as e:
                logger.error(f"DoH NS查询失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
        
        return []
    
    def _parse_dns_response_a(self, response_data: bytes) -> List[str]:
        """解析DNS响应中的A记录"""
        try:
            if len(response_data) < 12:
                return []
            
            # 解析头部
            header = struct.unpack('!HHHHHH', response_data[:12])
            answer_count = header[3]
            
            if answer_count == 0:
                return []
            
            # 跳过查询部分
            offset = 12
            
            # 跳过查询名称
            while offset < len(response_data) and response_data[offset] != 0:
                length = response_data[offset]
                if length > 63:  # 压缩指针
                    offset += 2
                    break
                offset += length + 1
            
            if offset < len(response_data) and response_data[offset] == 0:
                offset += 1
            
            offset += 4  # 跳过Type和Class
            
            # 解析答案
            ips = []
            for _ in range(answer_count):
                if offset >= len(response_data):
                    break
                
                # 跳过名称
                if response_data[offset] & 0xC0:  # 压缩指针
                    offset += 2
                else:
                    while offset < len(response_data) and response_data[offset] != 0:
                        offset += response_data[offset] + 1
                    offset += 1
                
                if offset + 10 > len(response_data):
                    break
                
                # 读取Type, Class, TTL, RDLength
                rr_data = struct.unpack('!HHIH', response_data[offset:offset+10])
                rr_type = rr_data[0]
                rd_length = rr_data[3]
                offset += 10
                
                # 如果是A记录 (Type 1) 且长度为4
                if rr_type == 1 and rd_length == 4 and offset + 4 <= len(response_data):
                    ip_bytes = response_data[offset:offset+4]
                    ip = '.'.join(str(b) for b in ip_bytes)
                    ips.append(ip)
                
                offset += rd_length
            
            return ips
            
        except Exception as e:
            logger.error(f"解析DNS响应失败: {e}")
            return []
    
    def _parse_dns_response_ns(self, response_data: bytes) -> List[str]:
        """解析DNS响应中的NS记录"""
        try:
            if len(response_data) < 12:
                return []
            
            # 解析头部
            header = struct.unpack('!HHHHHH', response_data[:12])
            answer_count = header[3]
            
            if answer_count == 0:
                return []
            
            # 跳过查询部分
            offset = 12
            
            # 跳过查询名称
            while offset < len(response_data) and response_data[offset] != 0:
                length = response_data[offset]
                if length > 63:  # 压缩指针
                    offset += 2
                    break
                offset += length + 1
            
            if offset < len(response_data) and response_data[offset] == 0:
                offset += 1
            
            offset += 4  # 跳过Type和Class
            
            # 解析答案
            ns_servers = []
            for _ in range(answer_count):
                if offset >= len(response_data):
                    break
                
                # 跳过名称
                if offset < len(response_data) and response_data[offset] & 0xC0:  # 压缩指针
                    offset += 2
                else:
                    while offset < len(response_data) and response_data[offset] != 0:
                        offset += response_data[offset] + 1
                    if offset < len(response_data):
                        offset += 1
                
                if offset + 10 > len(response_data):
                    break
                
                # 读取Type, Class, TTL, RDLength
                rr_data = struct.unpack('!HHIH', response_data[offset:offset+10])
                rr_type = rr_data[0]
                rd_length = rr_data[3]
                offset += 10
                
                # 如果是NS记录 (Type 2)
                if rr_type == 2 and offset + rd_length <= len(response_data):
                    ns_name = self._parse_domain_name(response_data, offset)
                    if ns_name:
                        ns_servers.append(ns_name)
                
                offset += rd_length
            
            return ns_servers
            
        except Exception as e:
            logger.error(f"解析NS记录失败: {e}")
            return []
    
    def _parse_domain_name(self, data: bytes, offset: int) -> str:
        """解析DNS响应中的域名（处理压缩指针）"""
        try:
            labels = []
            original_offset = offset
            jumped = False
            
            while offset < len(data):
                length = data[offset]
                
                if length == 0:
                    break
                elif length & 0xC0 == 0xC0:  # 压缩指针
                    if not jumped:
                        original_offset = offset + 2
                        jumped = True
                    # 计算指针位置
                    pointer = ((length & 0x3F) << 8) | data[offset + 1]
                    offset = pointer
                    continue
                else:
                    offset += 1
                    if offset + length > len(data):
                        break
                    label = data[offset:offset + length].decode('ascii', errors='ignore')
                    labels.append(label)
                    offset += length
            
            domain = '.'.join(labels)
            return domain if domain else ""
            
        except Exception as e:
            logger.error(f"解析域名失败: {e}")
            return "" 