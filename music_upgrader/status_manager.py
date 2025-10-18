#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音乐文件状态管理模块
定义音乐文件的各种状态枚举和状态管理器类
"""

from enum import Enum
from typing import List, Optional


# 定义状态枚举
class MusicStatus(Enum):
    MATCH_PENDING = "等待匹配"      # 等待匹配
    AUTO_MATCHED = "匹配(自动)"     # 匹配(自动)
    MANUAL_MATCHED = "匹配(手动)"   # 匹配(手动)
    MATCH_FAIL = "匹配失败"        # 匹配失败
    AUTO_DOWNLOAD_COMPLETE = "已下载(自动)"  # 已下载(自动)
    MANUAL_DOWNLOAD_COMPLETE = "已下载(手动)"  # 已下载(手动)
    DOWNLOAD_FAIL = "下载失败"     # 下载失败
    IGNORED = "已忽略"             # 已忽略


# 状态机管理类
class MusicStateManager:
    def __init__(self, num_items: int):
        # 当前状态列表
        self.status_list = [MusicStatus.MATCH_PENDING for _ in range(num_items)]
        # 保存被忽略前的状态列表，使用Optional[MusicStatus]类型
        self.ignored_status_backup = [None for _ in range(num_items)]  # type: List[Optional[MusicStatus]]

    def get_status(self, index: int) -> Optional[MusicStatus]:
        """获取指定索引的状态"""
        if 0 <= index < len(self.status_list):
            return self.status_list[index]
        return None

    def set_status(self, index: int, status: MusicStatus) -> bool:
        """设置指定索引的状态"""
        if 0 <= index < len(self.status_list):
            self.status_list[index] = status
            return True
        return False

    def ignore_item(self, index: int) -> bool:
        """忽略指定项"""
        if 0 <= index < len(self.status_list):
            # 保存当前状态
            self.ignored_status_backup[index] = self.status_list[index]
            # 设置为已忽略状态
            self.status_list[index] = MusicStatus.IGNORED
            return True
        return False

    def unignore_item(self, index: int) -> bool:
        """取消忽略指定项，恢复到之前的状态"""
        if 0 <= index < len(self.status_list) and self.ignored_status_backup[index] is not None:
            # 恢复到之前的状态
            previous_status = self.ignored_status_backup[index]
            if previous_status is not None:
                self.status_list[index] = previous_status
            # 清空备份状态
            self.ignored_status_backup[index] = None
            return True
        return False

    def can_ignore(self, index: int) -> bool:
        """检查是否可以忽略指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有在等待匹配、匹配失败、已忽略或匹配成功（但未下载）的状态下才能忽略
            # 不允许在下载完成之后忽略
            return current_status not in [MusicStatus.AUTO_DOWNLOAD_COMPLETE, MusicStatus.MANUAL_DOWNLOAD_COMPLETE]
        return False

    def can_manual_match(self, index: int) -> bool:
        """检查是否可以手动匹配指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 除了已忽略状态外，其他状态都可以手动匹配（包括已下载完成的歌曲）
            return current_status != MusicStatus.IGNORED
        return False

    def can_auto_match(self, index: int) -> bool:
        """检查是否可以自动匹配指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有等待匹配和匹配失败的状态可以自动匹配
            # 已忽略的项目不能自动匹配，因为如果在匹配之后被忽略，应该保留匹配信息，不参与下载
            # 如果需要重新匹配已忽略的项目，应该先取消忽略
            return current_status in [MusicStatus.MATCH_PENDING, MusicStatus.MATCH_FAIL]
        return False

    def can_download(self, index: int) -> bool:
        """检查是否可以下载指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有匹配成功的状态可以下载，且不能是已忽略的
            return current_status in [MusicStatus.AUTO_MATCHED, MusicStatus.MANUAL_MATCHED] and current_status != MusicStatus.IGNORED
        return False

    def can_unignore(self, index: int) -> bool:
        """检查是否可以取消忽略指定项"""
        if 0 <= index < len(self.status_list):
            current_status = self.status_list[index]
            # 只有已忽略的状态可以取消忽略
            return current_status == MusicStatus.IGNORED
        return False
