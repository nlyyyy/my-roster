import streamlit as st
import pandas as pd

# --- 页面基础配置 ---
st.set_page_config(layout="wide", page_title="智能排班管理系统")

# --- 管理员密码设置 ---
ADMIN_PASSWORD = "admin888"  # 你可以修改这个密码

# --- CSS 样式：报警灯 ---
st.markdown("""
    <style>
    .alarm-red { padding: 15px; background-color: #ff4b4b; color: white; border-radius: 8px; margin-bottom: 20px; font-size: 18px; }
    .alarm-green { padding: 15px; background-color: #28a745; color: white; border-radius: 8px; margin-bottom: 20px; font-size: 18px; }
    </style>
""", unsafe_allow_html=True)

# --- 权限控制逻辑 ---
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# --- 数据初始化 ---
if "staff_config" not in st.session_state:
    # 默认11人，月最大上班天数默认22天（参考中国法定工作日）
    st.session_state.staff_config = {f"人员{i:02d}": {"max_days": 22} for i in range(1, 12)}
if "prefs" not in st.session_state:
    st.session_state.prefs = {}

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
def generate_schedule(days, prefs, staff_config):
    staff_names = list(staff_config.keys())
    df = pd.DataFrame("休", index=staff_names, columns=range(1, days + 1))
    errors = []

    # 统计每个人的已排班天数
    work_days_count = {name: 0 for name in staff_names}
    
    # 统计连续上班天数
    consecutive_days = {name: 0 for name in staff_names}

    for d in range(1, days + 1):
        today_assigned = {name: p_type for (name, day), p_type in prefs.items() if day == d}
        
        # 检查偏好是否违反规则并更新统计
        for n, shift in today_assigned.items():
            if shift != "休":
                if consecutive_days[n] >= 6:
                    errors.append(f"{d}日 {n} 偏好冲突：已连续上班6天")
                if work_days_count[n] >= staff_config[n]["max_days"]:
                    errors.append(f"{d}日 {n} 偏好冲突：已达到月最大上班天数")
                
                work_days_count[n] += 1
                consecutive_days[n] += 1
            else:
                consecutive_days[n] = 0

        candidates = [n for n in staff_names if n not in today_assigned]
        
        # 填充 A 班 (5人)
        needed_a = max(0, 5 - list(today_assigned.values()).count("A"))
        
        # 过滤 A 班候选人：1. C不接A 2. 连续上班不超过6天 3. 月总天数不超过限制
        a_pool = [
            n for n in candidates 
            if not (d > 1 and df.at[n, d-1] == "C") 
            and consecutive_days[n] < 6 
            and work_days_count[n] < staff_config[n]["max_days"]
        ]
        
        # 排序：半月对调逻辑
        mid_point = len(staff_names) // 2
        a_pool.sort(key=lambda x: (staff_names.index(x) < mid_point) == (d <= 15), reverse=True)
        
        for n in a_pool[:needed_a]:
            today_assigned[n] = "A"
            work_days_count[n] += 1
            consecutive_days[n] += 1
            candidates.remove(n)

        # 填充 C 班 (4人)
        needed_c = max(0, 4 - list(today_assigned.values()).count("C"))
        
        # 过滤 C 班候选人：1. 连续上班不超过6天 2. 月总天数不超过限制
        c_pool = [
            n for n in candidates 
            if consecutive_days[n] < 6 
            and work_days_count[n] < staff_config[n]["max_days"]
        ]
        c_pool.sort(key=lambda x: (staff_names.index(x) >= mid_point) == (d <= 15), reverse=True)
        
        for n in c_pool[:needed_c]:
            today_assigned[n] = "C"
            work_days_count[n] += 1
            consecutive_days[n] += 1
            candidates.remove(n)

        # 最终赋值与状态重置
        for n in staff_names:
            shift = today_assigned.get(n, "休")
            df.at[n, d] = shift
            if shift == "休":
                consecutive_days[n] = 0
                
        if (df[d] == "A").sum() < 5: errors.append(f"{d}日A班不足")
        if (df[d] == "C").sum() < 4: errors.append(f"{d}日C班不足")
            
    return df, errors

# --- 主界面内容 ---
st.title("📅 智能排班在线管理平台")

# 仅管理员可见的操作区
if st.session_state.is_admin:
    with st.expander("🛠️ 管理员操作面板 - 录入偏好与人员管理", expanded=True):
        tab1, tab2 = st.tabs(["人员与规则管理", "录入偏好"])
        
        with tab1:
            col_a, col_b = st.columns(2)
            with col_a:
                new_staff = st.text_input("新增人员姓名")
                if st.button("➕ 添加人员"):
                    if new_staff and new_staff not in st.session_state.staff_config:
                        st.session_state.staff_config[new_staff] = {"max_days": 22}
                        st.rerun()
            with col_b:
                del_staff = st.selectbox("删除人员", list(st.session_state.staff_config.keys()))
                if st.button("🗑️ 删除人员"):
                    if del_staff in st.session_state.staff_config:
                        del st.session_state.staff_config[del_staff]
                        # 同时清除该人员的偏好
                        st.session_state.prefs = {k: v for k, v in st.session_state.prefs.items() if k[0] != del_staff}
                        st.rerun()
            
            if len(st.session_state.staff_config) < 9:
                st.warning("⚠️ 当前人员不足9人，无法满足每日 5A + 4C 的排班需求！")
            
            st.divider()
            st.write("配置人员月最大上班天数")
            for s_name in list(st.session_state.staff_config.keys()):
                col_s1, col_s2 = st.columns([2, 3])
                with col_s1:
                    st.write(f"**{s_name}**")
                with col_s2:
                    new_max = st.number_input(f"最大天数", 1, 31, st.session_state.staff_config[s_name]["max_days"], key=f"max_{s_name}")
                    st.session_state.staff_config[s_name]["max_days"] = new_max

        with tab2:
            col1, col2, col3 = st.columns(3)
            with col1:
                p_staff = st.selectbox("选择人员", list(st.session_state.staff_config.keys()), key="p_staff_select")
                p_day = st.number_input("选择日期", 1, 31, 1, key="p_day_input")
            with col2:
                p_type = st.radio("设定班次", ["休", "A", "C"], horizontal=True, key="p_type_radio")
                if st.button("➕ 提交偏好"):
                    st.session_state.prefs[(p_staff, p_day)] = p_type
                    st.rerun()
            with col3:
                if st.button("🗑️ 清空所有数据"):
                    st.session_state.prefs = {}
                    st.rerun()

# 执行排班
df, error_list = generate_schedule(31, st.session_state.prefs, st.session_state.staff_config)

# --- 报警灯显示 ---
if not error_list:
    st.markdown('<div class="alarm-green">🟢 状态正常：满足 5A + 4C 且符合所有衔接规则。</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="alarm-red">🔴 警告：{", ".join(error_list[:2])} 等冲突，请检查偏好。</div>', unsafe_allow_html=True)

# --- 班表展示 ---
st.subheader("当前最新排班表")
st.dataframe(df.style.applymap(lambda v: 'background-color: #d1e7dd' if v=='A' else ('background-color: #f8d7da' if v=='C' else 'color: #999')), use_container_width=True)

if st.session_state.is_admin:
    st.download_button("📥 点击下载 Excel 班表", df.to_csv().encode('utf-8-sig'), "排班表.csv")

