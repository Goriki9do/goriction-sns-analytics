"""
YouTube/TikTok/Instagram/Xの各exports CSVを1つのExcelにまとめる。

各SNSのfetchスクリプトを実行した後にこれを実行すると、
report/goriction_sns_report.xlsx が(既存があれば上書きで)作り直される。
VBAマクロは使わず、毎回Pythonでゼロから作り直す方式にしているので、
Excel起動時のマクロ有効化の警告も出ない。

使い方:
    python build_report.py
"""

import re
import sys
from pathlib import Path

import pandas as pd
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).parent.parent
OUTPUT_PATH = Path(__file__).parent / "goriction_sns_report.xlsx"


def to_naive_jst(series: pd.Series) -> pd.Series:
    """Excelはtz付きdatetimeを書けないので、JSTに変換してtz情報を外す。"""
    return series.dt.tz_convert("Asia/Tokyo").dt.tz_localize(None)


def make_label(date_short: pd.Series, caption: pd.Series, max_len: int = 10) -> pd.Series:
    """投稿ごとのグラフの横軸用に、日付+キャプション冒頭の短いラベルを作る。"""
    cap = caption.astype(str).str.replace(r"[\r\n]+", " ", regex=True)
    truncated = cap.str.slice(0, max_len) + cap.str.len().gt(max_len).map({True: "…", False: ""})
    return date_short.astype(str) + " " + truncated


def tiktok_sort_key(post_date: str) -> pd.Timestamp:
    """TikTok Studioの日付表示(例:「9月19日」)には年が無いので、
    グラフの並び順を作るためだけに便宜上2026年として解釈する。
    表示用のposted_at列はこれとは別に文字列のまま保持する。"""
    m = re.match(r"(\d+)月(\d+)日", str(post_date))
    if not m:
        return pd.NaT
    try:
        return pd.Timestamp(year=2026, month=int(m.group(1)), day=int(m.group(2)))
    except ValueError:
        return pd.NaT


COLUMNS = [
    "platform",
    "posted_at",
    "label",
    "caption",
    "likes",
    "views_or_impressions",
    "comments_raw",
    "unique_commenters",
    "permalink",
]
ALL_COLUMNS = COLUMNS + ["_sort_key"]


def load_youtube() -> pd.DataFrame:
    paths = list((ROOT / "youtube" / "exports_local").glob("*/videos.csv"))
    if not paths:
        print("youtube: exports_local/*/videos.csv が見つからんかった。スキップするで。")
        return pd.DataFrame(columns=ALL_COLUMNS)
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    posted_at = to_naive_jst(pd.to_datetime(df["published_at"], errors="coerce", utc=True))
    out = pd.DataFrame(
        {
            "platform": "YouTube",
            "posted_at": posted_at,
            "label": make_label(posted_at.dt.strftime("%m/%d"), df["title"]),
            "caption": df["title"],
            "likes": df["likes"],
            "views_or_impressions": df["views"],
            "comments_raw": df["comment_count_raw"],
            "unique_commenters": df["unique_commenters"],
            "permalink": "https://www.youtube.com/watch?v=" + df["video_id"].astype(str),
            "_sort_key": posted_at,
        }
    )
    return out


def load_tiktok() -> pd.DataFrame:
    path = ROOT / "tiktok" / "exports" / "videos.csv"
    if not path.exists():
        print("tiktok: exports/videos.csv が見つからんかった。スキップするで。")
        return pd.DataFrame(columns=ALL_COLUMNS)
    df = pd.read_csv(path)
    # 同じ動画が複数回fetchされていることがあるので、video_urlで最新のfetched_atだけ残す
    df = df.sort_values("fetched_at").drop_duplicates(subset="video_url", keep="last")
    sort_key = df["post_date"].apply(tiktok_sort_key)
    out = pd.DataFrame(
        {
            "platform": "TikTok",
            # TikTok Studioの日付表示には年が含まれない(例:「9月19日」)。
            # 年を跨ぐ蓄積時に誤認しないよう、表示用の値は日付として解釈せず文字列のまま保持する。
            "posted_at": df["post_date"].astype(str) + "(年不明)",
            "label": make_label(df["post_date"], df["title"]),
            "caption": df["title"],
            "likes": df["likes"],
            "views_or_impressions": df["views"],
            "comments_raw": df["comment_count_raw"],
            "unique_commenters": df["unique_commenters"],
            "permalink": df["video_url"],
            "_sort_key": sort_key,
        }
    )
    return out


def load_instagram() -> pd.DataFrame:
    path = ROOT / "instagram" / "exports" / "media.csv"
    if not path.exists():
        print("instagram: exports/media.csv が見つからんかった。スキップするで。")
        return pd.DataFrame(columns=ALL_COLUMNS)
    df = pd.read_csv(path)
    posted_at = to_naive_jst(pd.to_datetime(df["timestamp"], errors="coerce", utc=True))
    out = pd.DataFrame(
        {
            "platform": "Instagram",
            "posted_at": posted_at,
            "label": make_label(posted_at.dt.strftime("%m/%d"), df["caption"]),
            "caption": df["caption"],
            "likes": df["like_count"],
            "views_or_impressions": pd.NA,  # インサイト未実装のため表示回数は取得できていない
            "comments_raw": df["comment_count_raw"],
            "unique_commenters": df["unique_commenters"],
            "permalink": df["permalink"],
            "_sort_key": posted_at,
        }
    )
    return out


def load_x() -> pd.DataFrame:
    path = ROOT / "x" / "exports" / "posts.csv"
    if not path.exists():
        print("x: exports/posts.csv が見つからんかった。スキップするで。")
        return pd.DataFrame(columns=ALL_COLUMNS)
    df = pd.read_csv(path)
    posted_at = to_naive_jst(pd.to_datetime(df["created_at"], errors="coerce", utc=True))
    out = pd.DataFrame(
        {
            "platform": "X",
            "posted_at": posted_at,
            "label": make_label(posted_at.dt.strftime("%m/%d"), df["text"]),
            "caption": df["text"],
            "likes": df["like_count"],
            "views_or_impressions": df["impression_count"],
            "comments_raw": df["reply_count_raw"],
            "unique_commenters": df["unique_commenters"],
            "permalink": df["permalink"],
            "_sort_key": posted_at,
        }
    )
    return out


def build_summary(all_posts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for platform in ["YouTube", "TikTok", "Instagram", "X"]:
        sub = all_posts[all_posts["platform"] == platform]
        if sub.empty:
            continue
        rows.append(
            {
                "platform": platform,
                "投稿数": len(sub),
                "合計いいね": int(sub["likes"].fillna(0).sum()),
                "合計再生/表示回数": (
                    int(sub["views_or_impressions"].fillna(0).sum())
                    if sub["views_or_impressions"].notna().any()
                    else None
                ),
                "合計コメント/リプライ(raw)": int(sub["comments_raw"].fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def autosize_columns(ws) -> None:
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(length + 2, 60)


def add_bar_chart(ws, summary_row_count: int, value_col: int, title: str, anchor: str) -> None:
    chart = BarChart()
    chart.type = "col"
    chart.title = title
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    # カテゴリ(プラットフォーム)ごとに自動で色分けされるので、
    # どれがどの色か分かるように凡例は残す
    chart.legend.position = "b"

    data = Reference(ws, min_col=value_col, min_row=1, max_row=summary_row_count + 1)
    cats = Reference(ws, min_col=1, min_row=2, max_row=summary_row_count + 1)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)

    # 一番高いバーの数値ラベルがグラフタイトルと重ならないよう、上に余白を確保する
    values = [
        ws.cell(row=r, column=value_col).value
        for r in range(2, summary_row_count + 2)
    ]
    values = [v for v in values if isinstance(v, (int, float))]
    if values:
        chart.y_axis.scaling.max = max(values) * 1.2

    series = chart.series[0]
    series.varyColors = True
    series.dLbls = DataLabelList()
    series.dLbls.showVal = True
    series.dLbls.showCatName = False
    series.dLbls.showSerName = False
    series.dLbls.showLegendKey = False
    series.dLbls.numFmt = "#,##0"

    chart.height = 8
    chart.width = 13
    ws.add_chart(chart, anchor)


def add_post_chart(ws, row_count: int, value_col: int, color_hex: str, title: str, anchor: str) -> None:
    """label列(B列)を横軸に、投稿1件ごとの指標を投稿日の古い順に並べたグラフ。"""
    chart = BarChart()
    chart.type = "col"
    chart.title = title
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.x_axis.delete = False
    chart.y_axis.delete = False
    chart.legend = None

    data = Reference(ws, min_col=value_col, min_row=1, max_row=row_count + 1)
    cats = Reference(ws, min_col=2, min_row=2, max_row=row_count + 1)  # B列=label
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)

    values = [ws.cell(row=r, column=value_col).value for r in range(2, row_count + 2)]
    values = [v for v in values if isinstance(v, (int, float))]
    if values:
        chart.y_axis.scaling.max = max(values) * 1.2 if max(values) > 0 else 1

    series = chart.series[0]
    series.graphicalProperties.solidFill = color_hex
    series.dLbls = DataLabelList()
    series.dLbls.showVal = True
    series.dLbls.showCatName = False
    series.dLbls.showSerName = False
    series.dLbls.showLegendKey = False
    series.dLbls.numFmt = "#,##0"

    # 横軸のラベル(日付+キャプション冒頭)が全部読めるよう、投稿数に応じて幅を広げる
    chart.width = max(13, row_count * 1.3)
    chart.height = 8
    ws.add_chart(chart, anchor)


PLATFORM_COLORS = {
    "YouTube": "2a78d6",
    "TikTok": "eb6834",
    "Instagram": "1baf7a",
    "X": "eda100",
}


def main() -> None:
    frames = [load_youtube(), load_tiktok(), load_instagram(), load_x()]
    all_posts = pd.concat(frames, ignore_index=True)[ALL_COLUMNS]

    if all_posts.empty:
        print("どのSNSのデータも見つからんかった。各SNSのfetchスクリプトを先に実行してな。")
        sys.exit(1)

    summary = build_summary(all_posts)

    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="サマリー", index=False)

        for platform in ["YouTube", "TikTok", "Instagram", "X"]:
            sub = all_posts[all_posts["platform"] == platform].copy()
            if sub.empty:
                continue
            # 投稿ごとの推移グラフに使うので、いいね数ではなく投稿日の古い順に並べる
            sub = sub.sort_values("_sort_key", na_position="last")
            sub.drop(columns=["platform", "_sort_key"]).to_excel(writer, sheet_name=platform, index=False)

        notes = pd.DataFrame(
            {
                "注意点": [
                    "Instagramは現状いいね・コメント数のみ取得。表示回数/リーチ(インサイト)は未実装。",
                    "Xのリプライ取得は直近7日以内が対象。7日より前の投稿はunique_commentersが過小(0)になりうる。",
                    "TikTokの投稿日は年情報が無いため文字列のまま保持している(年跨ぎで誤認しないよう注意)。",
                    "YouTube/TikTokの再生回数とXのインプレッション(表示回数)は測定定義が異なる目安値。",
                    "このExcelはfetch時点のスナップショット。日々の推移を追うには過去分を別途残す必要がある。",
                ]
            }
        )
        notes.to_excel(writer, sheet_name="サマリー", index=False, startrow=len(summary) + 3)

    from openpyxl import load_workbook

    wb = load_workbook(OUTPUT_PATH)
    ws = wb["サマリー"]
    ws["A1"].font = Font(bold=True)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    autosize_columns(ws)

    chart_start_row = len(summary) + len(notes) + 6
    add_bar_chart(ws, len(summary), value_col=2, title="投稿数", anchor=f"A{chart_start_row}")
    add_bar_chart(ws, len(summary), value_col=3, title="合計いいね", anchor=f"A{chart_start_row + 18}")
    add_bar_chart(ws, len(summary), value_col=4, title="合計再生/表示回数", anchor=f"A{chart_start_row + 36}")

    for platform in ["YouTube", "TikTok", "Instagram", "X"]:
        if platform not in wb.sheetnames:
            continue
        psheet = wb[platform]
        autosize_columns(psheet)
        psheet["A1"].font = Font(bold=True)
        for cell in psheet[1]:
            cell.font = Font(bold=True)

        row_count = psheet.max_row - 1  # ヘッダー行を除いた投稿数
        color = PLATFORM_COLORS[platform]
        chart_row = row_count + 3
        add_post_chart(psheet, row_count, value_col=4, color_hex=color, title=f"{platform} いいね数(投稿ごと・古い順)", anchor=f"A{chart_row}")
        has_views = all_posts[all_posts["platform"] == platform]["views_or_impressions"].notna().any()
        if has_views:
            add_post_chart(psheet, row_count, value_col=5, color_hex=color, title=f"{platform} 再生/表示回数(投稿ごと・古い順)", anchor=f"A{chart_row + 20}")

    wb.save(OUTPUT_PATH)
    print(f"完了。{OUTPUT_PATH} に保存したで。")


if __name__ == "__main__":
    main()
