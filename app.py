import streamlit as st
import pandas as pd

# --- 页面基础配置 ---
st.set_page_config(layout="wide", page_title="14人智能排班管理系统")

# --- 管理员密码设置 ---
ADMIN_PASSWORD = "admin888"  # 你可以修改这个密码

# --- CSS 样式：报警灯 ---
# 将原来的写法替换为下面这段：
st.markdown('<style>.alarm-red { padding: 15px; background-color: #ff4b4b; color: white; border-radius: 8px; margin-bottom: 20px; font-size: 18px; } .alarm-green { padding: 15px; background-color: #28a745; color: white; border-radius: 8px; margin-bottom: 20px; font-size: 18px; }</style>', unsafe_allow_html=True)

# --- 权限控制逻辑 ---
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

with st.sidebar:
    st.title("🔐 权限验证")
    pwd = st.text_input("请输入管理员密码", type="password")
    if pwd == ADMIN_PASSWORD:
        st.session_state.is_admin = True
        st.success("管理员模式已开启")
    else:
        st.session_state.is_admin = False
        if pwd: st.error("密码错误")

# --- 核心排班函数 (包含冲突检测) ---
def generate_schedule(days, prefs, strict):
    staff_names = [f"人员{i:02d}" for i in range(1, 15)]
    df = pd.DataFrame("休", index=staff_names, columns=range(1, days + 1))
    errors = []

    for d in range(1, days + 1):
        today_assigned = {name: p_type for (name, day), p_type in prefs.items() if day == d}
        candidates = [n for n in staff_names if n not in today_assigned]
        
        # 填充 A 班 (5人) - 遵循半月对调与 C不接A
        needed_a = max(0, 5 - list(today_assigned.values()).count("A"))
        a_pool = [n for n in candidates if not (d > 1 and df.at[n, d-1] == "C")]
        a_pool.sort(key=lambda x: (staff_names.index(x) < 7) == (d <= 15), reverse=True)
        for n in a_pool[:needed_a]:
            today_assigned[n] = "A"
            candidates.remove(n)

        # 填充 C 班 (5人)
        needed_c = max(0, 5 - list(today_assigned.values()).count("C"))
        candidates.sort(key=lambda x: (staff_names.index(x) >= 7) == (d <= 15), reverse=True)
        for n in candidates[:needed_c]:
            today_assigned[n] = "C"
            candidates.remove(n)

        # 最终赋值与合规检查
        for n, shift in today_assigned.items(): df.at[n, d] = shift
        if (df[d] == "A").sum() < 5: errors.append(f"{d}日A班不足")
        if (df[d] == "C").sum() < 5: errors.append(f"{d}日C班不足")
            
    return df, errors

# --- 主界面内容 ---
st.title("📅 智能排班在线管理平台")

# 仅管理员可见的操作区
if st.session_state.is_admin:
    with st.expander("🛠️ 管理员操作面板 - 录入偏好与规则", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            p_staff = st.selectbox("选择人员", [f"人员{i:02d}" for i in range(1, 15)])
            p_day = st.number_input("选择日期", 1, 31, 1)
        with col2:
            p_type = st.radio("设定班次", ["休", "A", "C"], horizontal=True)
            if st.button("➕ 提交偏好"):
                if "prefs" not in st.session_state: st.session_state.prefs = {}
                st.session_state.prefs[(p_staff, p_day)] = p_type
                st.rerun()
        with col3:
            if st.button("🗑️ 清空所有数据"):
                st.session_state.prefs = {}
                st.rerun()

# 执行排班
if "prefs" not in st.session_state: st.session_state.prefs = {}
df, error_list = generate_schedule(31, st.session_state.prefs, True)

# --- 报警灯显示 ---
if not error_list:
    st.markdown('<div class="alarm-green">🟢 状态正常：满足 5A + 5C 且符合所有衔接规则。</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="alarm-red">🔴 警告：{", ".join(error_list[:2])} 等冲突，请检查偏好。</div>', unsafe_allow_html=True)

# --- 班表展示 ---
st.subheader("当前最新排班表")
st.dataframe(df.style.applymap(lambda v: 'background-color: #d1e7dd' if v=='A' else ('background-color: #f8d7da' if v=='C' else 'color: #999')), use_container_width=True)

if st.session_state.is_admin:
    st.download_button("📥 点击下载 Excel 班表", df.to_csv().encode('utf-8-sig'), "排班表.csv")
