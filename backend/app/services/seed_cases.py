from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.case import Case

logger = logging.getLogger(__name__)

SEED_CASES = [
    {
        'title': '工人未佩戴安全帽违规案例',
        'case_type': 'no_hardhat',
        'severity': 'high',
        'scene_description': (
            '监控显示一名工人在钢筋绑扎区域进行高处作业时未佩戴安全帽。'
            '该工人正在3米高的脚手架上进行钢筋绑扎作业，下方有其他工人交叉作业，'
            '存在物体打击风险。现场安全员未及时发现并制止该违规行为。'
        ),
        'recommended_actions': (
            '1. 立即要求工人停止作业并正确佩戴安全帽\n'
            '2. 对工人进行现场安全教育，强调高处作业佩戴安全帽的重要性\n'
            '3. 通知班组长加强监督，确保所有进入施工区域人员佩戴安全帽\n'
            '4. 将该案例纳入安全培训材料，全员通报\n'
            '5. 对现场安全员进行履职考核'
        ),
        'process_info': (
            '已通知班组长监督该工人立即佩戴安全帽，'
            '工人表示知晓并配合整改。项目部已将该案例在早班会上通报，'
            '并要求所有班组开展自查自纠。'
        ),
        'images': ['/uploads/images/seed_case_no_hardhat_1.jpg'],
    },
    {
        'title': '工人靠近挖掘机回转半径违规案例',
        'case_type': 'dangerous_operation',
        'severity': 'high',
        'scene_description': (
            '监控显示一名工人在挖掘机作业时进入挖掘机回转半径范围内。'
            '挖掘机正在进行基坑开挖作业，工人从挖掘机后方接近，'
            '试图从回转半径内穿过。挖掘机驾驶员视线受阻，未注意到该工人，'
            '存在严重的机械伤害风险。'
        ),
        'recommended_actions': (
            '1. 立即吹哨警告，要求工人撤离危险区域\n'
            '2. 在挖掘机周围设置明显的安全警示线和警示标志\n'
            '3. 设置机械作业警戒区，安排专人监护\n'
            '4. 对挖掘机驾驶员和工人进行安全交底\n'
            '5. 严格执行"人机分离"管理制度'
        ),
        'process_info': (
            '安全员已对当事人进行批评教育，并在挖掘机周围拉设警戒线。'
            '项目部召开专题安全会议，重申机械设备作业安全管理规定。'
        ),
        'images': ['/uploads/images/seed_case_dangerous_machinery_1.jpg'],
    },
    {
        'title': '施工车辆倒车区域人员穿行违规案例',
        'case_type': 'dangerous_operation',
        'severity': 'high',
        'scene_description': (
            '监控显示一辆自卸车在施工道路上倒车时，一名工人从车辆后方穿行。'
            '倒车区域未设置警示标志和警戒线，无专人指挥倒车。'
            '车辆倒车速度较慢，驾驶员未发现后方有人员穿行，存在车辆伤害风险。'
        ),
        'recommended_actions': (
            '1. 立即制止工人穿行行为，暂停车辆作业\n'
            '2. 在倒车区域设置明显的警示标志和警戒线\n'
            '3. 安排专人进行倒车指挥\n'
            '4. 车辆安装倒车影像和声光报警装置\n'
            '5. 对驾驶员和工人进行安全教育培训'
        ),
        'process_info': (
            '已要求项目部在所有施工车辆倒车区域设置警戒线，'
            '并安排专职信号工指挥倒车。车辆倒车报警装置已全部检修完毕。'
        ),
        'images': ['/uploads/images/seed_case_dangerous_vehicle_1.jpg'],
    },
    {
        'title': '作业人员进入锥形桶管控区违规案例',
        'case_type': 'dangerous_operation',
        'severity': 'medium',
        'scene_description': (
            '监控显示施工区域内设置了锥形桶警示区域，'
            '但多名作业人员为图方便穿越该管控区域。'
            '锥形桶围挡区域为临时材料堆放区，上方正在进行吊装作业，'
            '穿越行为存在被吊物打击的风险。'
        ),
        'recommended_actions': (
            '1. 加强管控区域周边警示标识设置\n'
            '2. 增派安全员在管控区域周边巡查\n'
            '3. 对违规穿越人员进行安全教育\n'
            '4. 优化施工通道布局，避免人员绕行过远\n'
            '5. 在管控区域设置语音提示装置'
        ),
        'process_info': (
            '已对违规穿越的工人进行安全教育，'
            '并在锥形桶区域增设安全警示牌和语音提示器。'
            '施工通道已重新规划，减少人员穿越管控区的需求。'
        ),
        'images': ['/uploads/images/seed_case_controlled_area_1.jpg'],
    },
    {
        'title': '电线杆下方违规堆放材料案例',
        'case_type': 'dangerous_operation',
        'severity': 'medium',
        'scene_description': (
            '监控显示施工人员在电线杆下方堆放钢管和模板等材料，'
            '材料堆放过高，距离电线杆过近。'
            '电线杆附近正在进行钢筋加工作业，'
            '存在触电和电线杆倒塌的双重安全隐患。'
        ),
        'recommended_actions': (
            '1. 立即清理电线杆下方堆放的施工材料\n'
            '2. 在电线杆周围设置安全警示区域\n'
            '3. 明确电线杆周边禁止堆料的范围\n'
            '4. 加强现场材料堆放管理，确保与电线杆保持安全距离\n'
            '5. 对相关班组进行安全交底'
        ),
        'process_info': (
            '已组织人员清理电线杆下方堆放的钢管和模板，'
            '并在电线杆周围设置警示桩和安全警示牌。'
            '材料堆放管理办法已更新并通知各班组执行。'
        ),
        'images': ['/uploads/images/seed_case_pole_area_1.jpg'],
    },
    {
        'title': '工人未穿戴反光背心违规案例',
        'case_type': 'other',
        'severity': 'low',
        'scene_description': (
            '监控显示一名工人在夜间施工时段未穿戴反光背心进入施工作业区。'
            '该区域有车辆和设备进出频繁，夜间照明条件有限，'
            '未穿戴反光背心导致人员辨识度低，存在车辆碰撞风险。'
        ),
        'recommended_actions': (
            '1. 要求工人立即穿戴反光背心后方可进入作业区\n'
            '2. 入口处设置反光背心穿戴检查点\n'
            '3. 加强夜间施工照明\n'
            '4. 对工人进行夜间施工安全培训\n'
            '5. 定期检查反光背心的配备和完好情况'
        ),
        'process_info': (
            '安全员已督促该工人穿戴反光背心，'
            '并在施工区入口设置反光背心穿戴提示牌。'
            '项目部已补充采购一批反光背心供工人使用。'
        ),
        'images': ['/uploads/images/seed_case_no_vest_1.jpg'],
    },
    {
        'title': '施工现场人员打斗事件案例',
        'case_type': 'other',
        'severity': 'high',
        'scene_description': (
            '监控显示两名工人在施工现场因工作分歧发生口角，'
            '情绪激动后升级为肢体冲突。周围多名工人围观，'
            '影响正常施工秩序，存在人员受伤的安全隐患。'
        ),
        'recommended_actions': (
            '1. 立即制止打斗行为，将双方分开\n'
            '2. 检查是否有人员受伤，及时送医\n'
            '3. 对涉事人员进行调查谈话\n'
            '4. 根据公司规定进行处理\n'
            '5. 加强班组管理，建立矛盾调解机制'
        ),
        'process_info': (
            '现场安全员和管理人员已及时制止冲突，'
            '双方均无受伤。项目部已对涉事工人进行批评教育，'
            '并根据考勤纪律规定进行处理。'
        ),
        'images': ['/uploads/images/seed_case_fight_1.jpg'],
    },
    {
        'title': '现场发现明火隐患案例',
        'case_type': 'other',
        'severity': 'critical',
        'scene_description': (
            '监控显示施工区域角落有工人在焚烧建筑垃圾，'
            '产生大量烟雾和明火。焚烧点靠近临时材料堆场，'
            '周围有木模板和保温材料等易燃物，'
            '且现场未配备灭火器材，存在严重的火灾隐患。'
        ),
        'recommended_actions': (
            '1. 立即扑灭明火，清理焚烧残留物\n'
            '2. 对当事人进行严肃批评教育\n'
            '3. 全面排查现场消防隐患\n'
            '4. 增配灭火器材到各作业区域\n'
            '5. 制定严格的施工现场用火管理制度'
        ),
        'process_info': (
            '明火已被立即扑灭，未造成财产损失和人员伤亡。'
            '项目部已对当事人进行警告处罚，'
            '并在全场开展消防安全专项整治行动。'
        ),
        'images': ['/uploads/images/seed_case_fire_1.jpg'],
    },
    {
        'title': '施工区域发现大量烟雾案例',
        'case_type': 'other',
        'severity': 'medium',
        'scene_description': (
            '监控显示施工区域某处升起大量烟雾，'
            '疑似电气设备短路或材料自燃。'
            '烟雾扩散速度快，能见度降低，'
            '影响周边作业人员的视线和呼吸，'
            '存在火灾和人员中毒的双重风险。'
        ),
        'recommended_actions': (
            '1. 立即疏散附近作业人员\n'
            '2. 查找烟雾来源，判断是否为火灾\n'
            '3. 如为火灾立即启动消防预案\n'
            '4. 检查电气线路和设备安全\n'
            '5. 清理易燃材料，加强消防巡查'
        ),
        'process_info': (
            '经现场排查，烟雾为电气设备短路引起，'
            '已及时切断电源并排除故障。'
            '项目部已对所有电气线路进行全面检查，'
            '并加强现场消防巡查频次。'
        ),
        'images': ['/uploads/images/seed_case_smoke_1.jpg'],
    },
    {
        'title': '高处作业人员防护不到位案例',
        'case_type': 'no_hardhat',
        'severity': 'medium',
        'scene_description': (
            '监控显示一名工人在2米以上高度的脚手架平台进行支模作业时，'
            '未正确佩戴安全帽（安全帽未系下颚带）。'
            '工人弯腰作业时安全帽脱落，险些掉落至下方作业区。'
            '工人未意识到风险，继续作业未重新佩戴好安全帽。'
        ),
        'recommended_actions': (
            '1. 要求工人立即停止作业，正确佩戴安全帽并系好下颚带\n'
            '2. 对工人进行现场安全教育\n'
            '3. 检查所有高处作业人员的安全防护用品佩戴情况\n'
            '4. 将安全帽正确佩戴方法纳入每日班前安全教育'
        ),
        'process_info': (
            '已要求该工人正确佩戴安全帽，'
            '并对其进行了再教育和培训。'
            '班组安全员已对所有高处作业人员的安全防护用品进行全面检查。'
        ),
        'images': ['/uploads/images/seed_case_no_hardhat_2.jpg'],
    },
]


def seed_cases(db: Session) -> int:
    from app.services.case_service import create_case
    from app.schemas.case import CaseCreate

    existing = db.query(Case).count()
    if existing > 0:
        logger.info(f'Cases table already has {existing} records, skipping seed')
        return 0

    count = 0
    for data in SEED_CASES:
        create_case(db, CaseCreate(**data))
        count += 1

    logger.info(f'Seeded {count} cases')
    return count
