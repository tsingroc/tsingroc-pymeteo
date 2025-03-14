from datetime import datetime
from typing import Optional, Tuple

import requests
import shapely.wkt as wkt
from shapely.geometry import Polygon
import numpy as np
import pandas as pd

from .auth import generate_aksk_authorization

__all__ = ["Meteo"]


class Meteo:
    def __init__(
        self,
        server_url: str,
        access_key: str,
        secret_key: str,
        proxies: Optional[dict] = None,
    ):
        """
        Args:
        - server_url (str): 服务器地址
        - access_key (str): 访问密钥
        - secret_key (str): 秘密密钥
        """

        self._server_url = server_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._proxies = proxies

    def get(
        self,
        table: str,
        dayplus: Optional[int],
        model: str,
        location: Polygon,
        time_range: Tuple[datetime, datetime],
        tilt_range: Optional[Tuple[float, float]] = None,
    ):
        """
        Args:
        - table (str): 数据表名
        - dayplus (Optional[int]): 日期偏移量
        - model (str): 气象模型名
        - location (Polygon): 查询区域
        - time_range (Tuple[datetime, datetime]): 起止时间范围，包含起止时间
        - tilt_range (Optional[Tuple[float, float]]): 倾角范围，设置为None代表不使用tilt进行筛选，否则使用倾角筛选，范围为闭区间，单位为度

        Returns:
        - dict: 查询结果
             - table_name (str): 数据表名
             - points (List[dict]): 查询结果
                - model (str): 气象模型名
                - location (str): 坐标点的 WKT 字符串
                - data (pd.DataFrame): 查询结果
             - cost (dict): 查询耗时
        """
        wkt_str = wkt.dumps(location)
        body = {
            "name": table,
            "dayplus": dayplus,
            "model": model,
            "location": wkt_str,
            "start_t": time_range[0].astimezone().isoformat(),
            "end_t": time_range[1].astimezone().isoformat(),
        }
        if tilt_range is not None:
            body["tilt_range"] = tilt_range
        # 发送请求
        authorization = generate_aksk_authorization(
            self._access_key, self._secret_key, {}
        )
        res = requests.post(
            self._server_url + "/api/meteo",
            json=body,
            headers={"Authorization": authorization},
        )
        if res.status_code != 200:
            raise Exception(f"请求失败，状态码：{res.status_code}, 原因：{res.text}")
        data = res.json()["data"]
        if data["points"] is None:
            data["points"] = []
        for point in data["points"]:
            ts = point["ts"]
            params = point["params"]
            if table == "ensemble_cn":
                assert len(params) == len(point["values"])
                value_box = np.empty((len(params), len(ts)), dtype=object)
                for i, values in enumerate(point["values"]):
                    assert len(ts) == len(values)
                    for j in range(len(ts)):
                        value_box[i, j] = values[j]
                value_box = value_box.T
                df = pd.DataFrame(value_box, columns=params, index=pd.to_datetime(ts))
                point["data"] = df
            else:
                values = np.array(point["values"], dtype=np.float32).T
                df = pd.DataFrame(values, columns=params, index=pd.to_datetime(ts))
                point["data"] = df
            del point["ts"]
            del point["params"]
            del point["values"]
        return data
