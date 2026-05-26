# 综测加分项目完整目录 - 基于《2025年7月电信学院综测细则》
# 每个项目: id, category, subcategory, title, description, level, score, icon, note, limit

CATALOG = [
    # ==================== 品德行为表现 (30分附加) ====================
    # --- (1) 担任学生干部满一年 ---
    # 校级组织 - 学生会
    {"id":"M001","category":"moral","subcategory":"student_cadre","title":"校学生会主席团（正）","description":"担任校学生会主席团正式成员满一年","level":"校级","score":12,"icon":"fa-crown","section":"学生干部"},
    {"id":"M002","category":"moral","subcategory":"student_cadre","title":"校学生会主席团（副）","description":"担任校学生会主席团副职满一年","level":"校级","score":10,"icon":"fa-crown","section":"学生干部"},
    {"id":"M003","category":"moral","subcategory":"student_cadre","title":"校学生会部长（正）","description":"担任校学生会部长正职满一年","level":"校级","score":6,"icon":"fa-user-tie","section":"学生干部"},
    {"id":"M004","category":"moral","subcategory":"student_cadre","title":"校学生会部长（副）","description":"担任校学生会部长副职满一年","level":"校级","score":5,"icon":"fa-user-tie","section":"学生干部"},
    {"id":"M005","category":"moral","subcategory":"student_cadre","title":"校学生会干事","description":"担任校学生会干事满一年","level":"校级","score":3,"icon":"fa-user","section":"学生干部"},
    # 校级组织 - 其他
    {"id":"M006","category":"moral","subcategory":"student_cadre","title":"校学生社团联合会主席团","description":"担任校社联主席团成员满一年","level":"校级","score":10,"icon":"fa-users","section":"学生干部"},
    {"id":"M007","category":"moral","subcategory":"student_cadre","title":"校学生社团联合会部长/干事","description":"担任校社联部长6分/干事3分满一年","level":"校级","score":6,"icon":"fa-users","section":"学生干部"},
    {"id":"M008","category":"moral","subcategory":"student_cadre","title":"校青年志愿者协会主席团","description":"担任校青协主席团满一年","level":"校级","score":10,"icon":"fa-hand-holding-heart","section":"学生干部"},
    {"id":"M009","category":"moral","subcategory":"student_cadre","title":"校青年志愿者协会部长/干事","description":"担任校青协部长6分/干事3分满一年","level":"校级","score":6,"icon":"fa-hand-holding-heart","section":"学生干部"},
    {"id":"M010","category":"moral","subcategory":"student_cadre","title":"校红十字会主席团","description":"担任校红会主席团满一年","level":"校级","score":10,"icon":"fa-plus-circle","section":"学生干部"},
    {"id":"M011","category":"moral","subcategory":"student_cadre","title":"校自律委员会主席团/部长/干事","description":"担任校自律委员会职务满一年","level":"校级","score":6,"icon":"fa-shield-alt","section":"学生干部"},
    {"id":"M012","category":"moral","subcategory":"student_cadre","title":"校勤工助学中心/广播站","description":"担任校勤工助学中心或广播站主席团10分/部长6分满一年","level":"校级","score":6,"icon":"fa-broadcast-tower","section":"学生干部"},
    {"id":"M013","category":"moral","subcategory":"student_cadre","title":"校艺术团主席团/分团长","description":"担任校艺术团主席团10分/分团团长6分满一年","level":"校级","score":10,"icon":"fa-music","section":"学生干部"},
    {"id":"M014","category":"moral","subcategory":"student_cadre","title":"国旗护卫队队长/部长/队员","description":"担任国旗护卫队职务满一年","level":"校级","score":6,"icon":"fa-flag","section":"学生干部"},
    {"id":"M015","category":"moral","subcategory":"student_cadre","title":"《广师大学生》编辑部","description":"担任编辑部责编4分/站长(正6副5)/组长(正4副3)满一年","level":"校级","score":4,"icon":"fa-newspaper","section":"学生干部"},
    {"id":"M016","category":"moral","subcategory":"student_cadre","title":"校辩论队队长/队员","description":"担任校辩论队职务满一年","level":"校级","score":5,"icon":"fa-comments","section":"学生干部"},
    {"id":"M017","category":"moral","subcategory":"student_cadre","title":"学生处及校团委工作助理","description":"担任学生处或校团委工作助理满一年","level":"校级","score":8,"icon":"fa-briefcase","section":"学生干部"},
    {"id":"M018","category":"moral","subcategory":"student_cadre","title":"广师视频成员","description":"担任广师视频成员满一年","level":"校级","score":6,"icon":"fa-video","section":"学生干部"},
    # 院级组织
    {"id":"M019","category":"moral","subcategory":"student_cadre","title":"院团总支学生会主席/团总支副书记","description":"担任院学生会主席或团总支副书记满一年","level":"院级","score":10,"icon":"fa-star","section":"学生干部"},
    {"id":"M020","category":"moral","subcategory":"student_cadre","title":"院团总支学生会部长","description":"担任院学生会部长满一年","level":"院级","score":6,"icon":"fa-star","section":"学生干部"},
    {"id":"M021","category":"moral","subcategory":"student_cadre","title":"院团总支学生会干事","description":"担任院学生会干事满一年","level":"院级","score":4,"icon":"fa-user","section":"学生干部"},
    {"id":"M022","category":"moral","subcategory":"student_cadre","title":"院团总支学生会预干","description":"担任院学生会预干满一年","level":"院级","score":1,"icon":"fa-user","section":"学生干部"},
    {"id":"M023","category":"moral","subcategory":"student_cadre","title":"院科技站技术部（优秀）","description":"科技站技术部考核优秀满一年","level":"院级","score":10,"icon":"fa-microchip","section":"学生干部"},
    {"id":"M024","category":"moral","subcategory":"student_cadre","title":"院科技站技术部（合格）","description":"科技站技术部考核合格满一年","level":"院级","score":5,"icon":"fa-microchip","section":"学生干部"},
    {"id":"M025","category":"moral","subcategory":"student_cadre","title":"院科技站秘书部部长/成员","description":"科技站秘书部部长8分/成员6分满一年","level":"院级","score":8,"icon":"fa-microchip","section":"学生干部"},
    {"id":"M026","category":"moral","subcategory":"student_cadre","title":"院学生党支部副书记/委员","description":"院学生党支部副书记6分/其他委员5分","level":"院级","score":6,"icon":"fa-building","section":"学生干部"},
    {"id":"M027","category":"moral","subcategory":"student_cadre","title":"医保/综测/助学贷款/心理/就业/党务小组组长","description":"各院级小组组长7分/组员5分满一年","level":"院级","score":7,"icon":"fa-clipboard-list","section":"学生干部"},
    {"id":"M028","category":"moral","subcategory":"student_cadre","title":"辅导员助理","description":"担任辅导员助理满一年","level":"院级","score":6,"icon":"fa-chalkboard-teacher","section":"学生干部"},
    {"id":"M029","category":"moral","subcategory":"student_cadre","title":"助理班主任","description":"担任助理班主任满一年","level":"院级","score":6,"icon":"fa-user-graduate","section":"学生干部"},
    {"id":"M030","category":"moral","subcategory":"student_cadre","title":"助部","description":"担任助部满一年","level":"院级","score":3,"icon":"fa-user-cog","section":"学生干部"},
    # 班级
    {"id":"M031","category":"moral","subcategory":"student_cadre","title":"班长/团支书","description":"担任班长或团支书满一年","level":"班级","score":8,"icon":"fa-user-tie","section":"学生干部"},
    {"id":"M032","category":"moral","subcategory":"student_cadre","title":"副班长","description":"担任副班长满一年","level":"班级","score":6,"icon":"fa-user-tie","section":"学生干部"},
    {"id":"M033","category":"moral","subcategory":"student_cadre","title":"学习委员","description":"担任学习委员满一年","level":"班级","score":6,"icon":"fa-book","section":"学生干部"},
    {"id":"M034","category":"moral","subcategory":"student_cadre","title":"纪律委员","description":"担任纪律委员满一年","level":"班级","score":5,"icon":"fa-gavel","section":"学生干部"},
    {"id":"M035","category":"moral","subcategory":"student_cadre","title":"其他班干部（含信息员）","description":"担任其他班干满一年","level":"班级","score":4,"icon":"fa-user","section":"学生干部"},
    {"id":"M036","category":"moral","subcategory":"student_cadre","title":"宿舍长","description":"担任宿舍长满一年","level":"班级","score":2,"icon":"fa-home","section":"学生干部"},
    # 社团
    {"id":"M037","category":"moral","subcategory":"student_cadre","title":"社团会长","description":"担任社团会长满一年","level":"院级","score":3,"icon":"fa-users","section":"学生干部"},
    {"id":"M038","category":"moral","subcategory":"student_cadre","title":"社团正副部长","description":"担任社团正副部长满一年","level":"院级","score":2,"icon":"fa-users","section":"学生干部"},
    {"id":"M039","category":"moral","subcategory":"student_cadre","title":"社团干事","description":"担任社团干事满一年","level":"院级","score":1,"icon":"fa-user","section":"学生干部"},

    # --- (2) 在纸质刊物上发表文章 ---
    {"id":"M040","category":"moral","subcategory":"publication","title":"校级刊物发表文章","description":"在校级纸质刊物上发表文章","level":"校级","score":3,"icon":"fa-pen-fancy","section":"发表文章","note":"每篇3分，上限10分"},
    {"id":"M041","category":"moral","subcategory":"publication","title":"院级刊物发表文章","description":"在院级纸质刊物上发表文章","level":"院级","score":1,"icon":"fa-pen-fancy","section":"发表文章","note":"每篇1分，上限10分"},

    # --- (3) 参加活动 ---
    {"id":"M042","category":"moral","subcategory":"activity","title":"参加校级/校外思想教育类活动","description":"参加校院举办的各类活动（推优会议除外）","level":"校级","score":2,"icon":"fa-calendar-check","section":"参加活动","note":"每次2分，可累加"},
    {"id":"M043","category":"moral","subcategory":"activity","title":"参加院级思想教育类活动","description":"参加院级活动或团日活动","level":"院级","score":2,"icon":"fa-calendar-check","section":"参加活动","note":"每次2分"},
    {"id":"M044","category":"moral","subcategory":"activity","title":"活动获奖（校级/校外第一名）","description":"参加活动获校级或校外县级以上第一名","level":"校级","score":3,"icon":"fa-trophy","section":"参加活动","note":"在参加分基础上另加"},
    {"id":"M045","category":"moral","subcategory":"activity","title":"活动获奖（校级/校外第二、三名）","description":"参加活动获校级或校外县级以上第二或第三名","level":"校级","score":2,"icon":"fa-medal","section":"参加活动","note":"在参加分基础上另加"},
    {"id":"M046","category":"moral","subcategory":"activity","title":"活动获奖（院级第一名）","description":"参加院级活动获第一名","level":"院级","score":2,"icon":"fa-medal","section":"参加活动","note":"在参加分基础上另加"},
    {"id":"M047","category":"moral","subcategory":"activity","title":"活动获奖（院级其他奖）","description":"参加院级活动获非第一名奖项","level":"院级","score":1,"icon":"fa-award","section":"参加活动","note":"在参加分基础上另加"},
    {"id":"M048","category":"moral","subcategory":"volunteer","title":"志愿活动/义务劳动（每4小时）","description":"参加志愿活动、义务劳动","level":"院级","score":1,"icon":"fa-hand-holding-heart","section":"志愿活动","note":"每4小时1分，上限12分；负责学生干部折半"},
    {"id":"M049","category":"moral","subcategory":"activity","title":"三下乡活动（参加）","description":"参加三下乡社会实践活动","level":"校级","score":5,"icon":"fa-sun","section":"参加活动","note":"参加多支队伍不重复加分"},
    {"id":"M050","category":"moral","subcategory":"activity","title":"三下乡活动（获校级奖）","description":"参加三下乡获校级奖","level":"校级","score":10,"icon":"fa-sun","section":"参加活动","note":"获校级奖另加"},
    {"id":"M051","category":"moral","subcategory":"activity","title":"三下乡活动（获省级奖）","description":"参加三下乡获省级奖","level":"省级","score":15,"icon":"fa-sun","section":"参加活动","note":"获省级奖另加"},

    # --- (4) 获荣誉称号 ---
    {"id":"M052","category":"moral","subcategory":"honor","title":"省级优秀学生干部/优秀团干/优秀团员/积极分子","description":"获评省级荣誉称号","level":"省级","score":15,"icon":"fa-award","section":"荣誉称号","note":"以最高三个荣誉称号加分"},
    {"id":"M053","category":"moral","subcategory":"honor","title":"校级优秀学生干部/优秀团干/优秀团员/积极分子","description":"获评校级荣誉称号","level":"校级","score":10,"icon":"fa-award","section":"荣誉称号"},
    {"id":"M054","category":"moral","subcategory":"honor","title":"院级优秀学生干部/优秀团干/优秀团员/积极分子","description":"获评院级荣誉称号","level":"院级","score":5,"icon":"fa-award","section":"荣誉称号"},
    {"id":"M055","category":"moral","subcategory":"honor","title":"军训先进个人/军训优秀学生干部","description":"获评军训先进个人或优秀学生干部","level":"校级","score":6,"icon":"fa-shield-alt","section":"荣誉称号"},
    {"id":"M056","category":"moral","subcategory":"honor","title":"军训副排长/副连长","description":"担任军训副排长或副连长","level":"校级","score":2,"icon":"fa-shield-alt","section":"荣誉称号"},
    {"id":"M057","category":"moral","subcategory":"honor","title":"军训单项奖（军训积极分子等）","description":"获得军训单项奖","level":"校级","score":5,"icon":"fa-shield-alt","section":"荣誉称号"},
    {"id":"M058","category":"moral","subcategory":"honor","title":"校级文体先进个人","description":"获评校级文体先进个人","level":"校级","score":5,"icon":"fa-star","section":"荣誉称号"},
    {"id":"M059","category":"moral","subcategory":"honor","title":"院级文体先进个人","description":"获评院级文体先进个人","level":"院级","score":2,"icon":"fa-star","section":"荣誉称号"},
    {"id":"M060","category":"moral","subcategory":"honor","title":"献血先进个人","description":"获评献血先进个人","level":"校级","score":3,"icon":"fa-heart","section":"荣誉称号"},
    {"id":"M061","category":"moral","subcategory":"honor","title":"校学生处/团委/学生会通报表扬","description":"受到校级组织通报表扬","level":"校级","score":3,"icon":"fa-thumbs-up","section":"荣誉称号"},
    {"id":"M062","category":"moral","subcategory":"honor","title":"科技站学术之星","description":"获评科技站学术之星","level":"院级","score":5,"icon":"fa-microscope","section":"荣誉称号"},

    # --- (5) 好人好事 ---
    {"id":"M063","category":"moral","subcategory":"good_deed","title":"无偿献血","description":"参加无偿献血活动","level":"校级","score":5,"icon":"fa-heart","section":"好人好事","note":"每次加5分"},
    {"id":"M064","category":"moral","subcategory":"good_deed","title":"见义勇为","description":"见义勇为行为","level":"校级","score":5,"icon":"fa-shield-virus","section":"好人好事"},
    {"id":"M065","category":"moral","subcategory":"good_deed","title":"乐于助人/特殊贡献（通报表扬）","description":"有乐于助人或特殊贡献行为经通报表扬","level":"校级","score":3,"icon":"fa-smile","section":"好人好事","note":"由辅导员酌情加分"},

    # --- (6) 文明宿舍 ---
    {"id":"M066","category":"moral","subcategory":"dormitory","title":"校级文明宿舍标兵","description":"所在宿舍获评校级文明宿舍标兵","level":"校级","score":10,"icon":"fa-home","section":"文明宿舍","note":"每人加10分"},
    {"id":"M067","category":"moral","subcategory":"dormitory","title":"校级文明宿舍","description":"所在宿舍获评校级文明宿舍","level":"校级","score":8,"icon":"fa-home","section":"文明宿舍","note":"每人加8分"},
    {"id":"M068","category":"moral","subcategory":"dormitory","title":"院级文明宿舍标兵","description":"所在宿舍获评院级文明宿舍标兵","level":"院级","score":8,"icon":"fa-home","section":"文明宿舍","note":"每人加8分"},
    {"id":"M069","category":"moral","subcategory":"dormitory","title":"院级文明宿舍","description":"所在宿舍获评院级文明宿舍","level":"院级","score":6,"icon":"fa-home","section":"文明宿舍","note":"每人加6分；校院以最高级加分"},

    # --- (7) 承办活动 ---
    {"id":"M070","category":"moral","subcategory":"organize","title":"承办院级以上活动（班级成员）","description":"班级承办院级以上活动，参与成员加分","level":"院级","score":2,"icon":"fa-tasks","section":"承办活动","note":"每人加2分"},
    {"id":"M071","category":"moral","subcategory":"organize","title":"协办院级以上活动","description":"协办院级以上活动","level":"院级","score":1,"icon":"fa-tasks","section":"承办活动","note":"每人加1分，上限10分；不参加者不加分"},
    {"id":"M072","category":"moral","subcategory":"organize","title":"优秀承办/协办班集体","description":"获评优秀承办或协办班集体","level":"院级","score":4,"icon":"fa-tasks","section":"承办活动","note":"按两倍加分"},

    # --- (8) 办公室值班 ---
    {"id":"M073","category":"moral","subcategory":"duty","title":"院办公室/党建办公室值班","description":"参与院办公室或党建办公室值班，工作认真不迟到早退","level":"院级","score":1,"icon":"fa-clock","section":"值班","note":"每次1分，一学期上限3分"},

    # --- (9) 参加代表大会 ---
    {"id":"M074","category":"moral","subcategory":"congress","title":"参加国家级代表大会","description":"经院审核参加国家级代表大会","level":"国家级","score":5,"icon":"fa-landmark","section":"代表大会"},
    {"id":"M075","category":"moral","subcategory":"congress","title":"参加省级代表大会","description":"经院审核参加省级代表大会","level":"省级","score":3,"icon":"fa-landmark","section":"代表大会"},
    {"id":"M076","category":"moral","subcategory":"congress","title":"参加市级代表大会","description":"经院审核参加市级代表大会","level":"校级","score":2,"icon":"fa-landmark","section":"代表大会"},
    {"id":"M077","category":"moral","subcategory":"congress","title":"参加校/院团学代会","description":"参加校或院团学代会","level":"校级","score":1.5,"icon":"fa-landmark","section":"代表大会"},

    # --- (10) 班集体获奖 ---
    {"id":"M078","category":"moral","subcategory":"class_award","title":"省级班集体获奖 - 班长/团支书","description":"班级获省级表彰，班长或团支书加分","level":"省级","score":8,"icon":"fa-trophy","section":"班集体获奖"},
    {"id":"M079","category":"moral","subcategory":"class_award","title":"省级班集体获奖 - 班内团员","description":"班级获省级表彰，班内团员加分","level":"省级","score":3,"icon":"fa-trophy","section":"班集体获奖"},
    {"id":"M080","category":"moral","subcategory":"class_award","title":"校级班集体获奖 - 班长/团支书","description":"班级获校级表彰，班长或团支书加分","level":"校级","score":5,"icon":"fa-medal","section":"班集体获奖"},
    {"id":"M081","category":"moral","subcategory":"class_award","title":"校级班集体获奖 - 班内团员（前5名）","description":"班级获校级表彰，团员加分","level":"校级","score":3,"icon":"fa-medal","section":"班集体获奖"},
    {"id":"M082","category":"moral","subcategory":"class_award","title":"校级班集体获奖 - 班内团员","description":"班级获校级表彰","level":"校级","score":1,"icon":"fa-medal","section":"班集体获奖"},

    # ==================== 学业表现 (20分附加) ====================
    # --- (1) 学术论文 ---
    {"id":"A001","category":"academic","subcategory":"paper","title":"发表/宣读学术论文（国家级）","description":"在国家级学术会议上发表或宣读学术论文","level":"国家级","score":15,"icon":"fa-file-alt","section":"学术论文","note":"15分/篇"},
    {"id":"A002","category":"academic","subcategory":"paper","title":"发表/宣读学术论文（省级）","description":"在省级学术会议上发表或宣读学术论文","level":"省级","score":10,"icon":"fa-file-alt","section":"学术论文","note":"10分/篇"},
    {"id":"A003","category":"academic","subcategory":"paper","title":"发表/宣读学术论文（校级）","description":"在校级学术会议上发表或宣读学术论文","level":"校级","score":5,"icon":"fa-file-alt","section":"学术论文","note":"5分/篇"},
    {"id":"A004","category":"academic","subcategory":"paper","title":"经院推荐向学术讨论会提交论文（国家级）","description":"经院审查推荐向全国学术讨论会提交论文","level":"国家级","score":10,"icon":"fa-file-alt","section":"学术论文","note":"10分/篇"},
    {"id":"A005","category":"academic","subcategory":"paper","title":"经院推荐向学术讨论会提交论文（省级）","description":"经院审查推荐向省级学术讨论会提交论文","level":"省级","score":8,"icon":"fa-file-alt","section":"学术论文","note":"8分/篇"},
    {"id":"A006","category":"academic","subcategory":"paper","title":"经院推荐向学术讨论会提交论文（校级）","description":"经院审查推荐向校级学术讨论会提交论文","level":"校级","score":5,"icon":"fa-file-alt","section":"学术论文","note":"5分/篇"},

    # --- (2) 重点科技竞赛 ---
    {"id":"A007","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（国家级最高奖）","description":"国家级最高奖（特等奖/一等奖）","level":"国家级","score":40,"icon":"fa-trophy","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A008","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（省级最高奖）","description":"省级最高奖（特等奖/一等奖）","level":"省级","score":40,"icon":"fa-trophy","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A009","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（省级次级奖）","description":"省级次级奖（二等奖）","level":"省级","score":25,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A010","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（省级三等奖）","description":"省级三等奖","level":"省级","score":15,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A011","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（省级参赛/四等奖）","description":"省级其他奖项或参赛选手","level":"省级","score":8,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A012","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（校级最高奖）","description":"校级最高奖（特等奖/一等奖）","level":"校级","score":10,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A013","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（校级次级奖）","description":"校级次级奖（二等奖）","level":"校级","score":8,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A014","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（校级三等奖/参赛）","description":"校级三等奖或参赛选手","level":"校级","score":4,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A015","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（院级最高奖）","description":"院级最高奖","level":"院级","score":8,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A016","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（院级次级奖）","description":"院级次级奖","level":"院级","score":6,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},
    {"id":"A017","category":"academic","subcategory":"key_competition","title":"互联网+/大挑/小挑/电子设计竞赛（院级三等奖/参赛）","description":"院级三等奖或参赛选手","level":"院级","score":2,"icon":"fa-medal","section":"重点科技竞赛","note":"前3名100%，4-5名70%，其余25%"},

    # --- (3) 立项项目 ---
    {"id":"A018","category":"academic","subcategory":"innovation_project","title":"攀登计划立项（国家级）- 负责人","description":"攀登计划国家级立项，担任负责人","level":"国家级","score":20,"icon":"fa-project-diagram","section":"科研立项","note":"负责人100%，2-3名80%，其余30%"},
    {"id":"A019","category":"academic","subcategory":"innovation_project","title":"攀登计划立项（国家级）- 核心成员","description":"攀登计划国家级立项，排名2-3","level":"国家级","score":16,"icon":"fa-project-diagram","section":"科研立项","note":"按负责人分数的80%"},
    {"id":"A020","category":"academic","subcategory":"innovation_project","title":"攀登计划立项（省级）- 负责人","description":"攀登计划省级立项，担任负责人","level":"省级","score":13,"icon":"fa-project-diagram","section":"科研立项","note":"负责人100%"},
    {"id":"A021","category":"academic","subcategory":"innovation_project","title":"攀登计划立项（校级）- 负责人","description":"攀登计划校级立项，担任负责人","level":"校级","score":7,"icon":"fa-project-diagram","section":"科研立项","note":"负责人100%"},
    {"id":"A022","category":"academic","subcategory":"innovation_project","title":"大创重点立项+结项（国家级）- 负责人","description":"大创国家级重点立项并结项，担任负责人","level":"国家级","score":20,"icon":"fa-lightbulb","section":"科研立项","note":"立项10+结项10；负责人100%，2-5名60%"},
    {"id":"A023","category":"academic","subcategory":"innovation_project","title":"大创普通立项+结项（国家级）- 负责人","description":"大创国家级普通立项并结项","level":"国家级","score":16,"icon":"fa-lightbulb","section":"科研立项","note":"立项8+结项8"},
    {"id":"A024","category":"academic","subcategory":"innovation_project","title":"大创重点立项+结项（省级）- 负责人","description":"大创省级重点立项并结项，担任负责人","level":"省级","score":14,"icon":"fa-lightbulb","section":"科研立项","note":"立项7+结项7"},
    {"id":"A025","category":"academic","subcategory":"innovation_project","title":"大创立项+结项（校级）- 负责人","description":"大创校级立项并结项","level":"校级","score":6,"icon":"fa-lightbulb","section":"科研立项","note":"立项3+结项3"},

    # --- (5) 其他各类竞赛 ---
    {"id":"A026","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（国家级一等奖/特等奖）","description":"国家级专业相关竞赛最高奖","level":"国家级","score":15,"icon":"fa-trophy","section":"其他竞赛","note":"专业相关→学业；非专业→文体"},
    {"id":"A027","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（国家级二等奖）","description":"国家级二等奖","level":"国家级","score":12,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A028","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（国家级三等奖）","description":"国家级三等奖","level":"国家级","score":10,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A029","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（国家级其他奖）","description":"国家级其他奖项","level":"国家级","score":6,"icon":"fa-award","section":"其他竞赛"},
    {"id":"A030","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（省级一等奖/特等奖）","description":"省级一等奖或特等奖","level":"省级","score":10,"icon":"fa-trophy","section":"其他竞赛"},
    {"id":"A031","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（省级二等奖）","description":"省级二等奖","level":"省级","score":8,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A032","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（省级三等奖）","description":"省级三等奖","level":"省级","score":6,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A033","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（省级其他奖）","description":"省级其他奖项","level":"省级","score":4,"icon":"fa-award","section":"其他竞赛"},
    {"id":"A034","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（校级一等奖）","description":"校级一等奖或特等奖","level":"校级","score":5,"icon":"fa-trophy","section":"其他竞赛"},
    {"id":"A035","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（校级二等奖）","description":"校级二等奖","level":"校级","score":4,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A036","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（校级三等奖）","description":"校级三等奖","level":"校级","score":3,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A037","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（校级其他奖/参赛）","description":"校级其他奖项或参赛","level":"校级","score":2,"icon":"fa-award","section":"其他竞赛"},
    {"id":"A038","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（院级一等奖）","description":"院级一等奖或特等奖","level":"院级","score":4,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A039","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（院级二等奖）","description":"院级二等奖","level":"院级","score":3,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A040","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（院级三等奖）","description":"院级三等奖","level":"院级","score":2,"icon":"fa-medal","section":"其他竞赛"},
    {"id":"A041","category":"academic","subcategory":"other_competition","title":"其他专业竞赛（院级其他奖/参赛）","description":"院级其他奖项或参赛","level":"院级","score":1,"icon":"fa-award","section":"其他竞赛","note":"每次参赛+1分，每类最高3分"},

    # --- (6) 英语等级 ---
    {"id":"A042","category":"academic","subcategory":"english","title":"英语四级（CET-4 ≥425分）","description":"通过大学英语四级考试","level":"国家级","score":8,"icon":"fa-language","section":"英语证书","note":"同一年过四六级可同时加分"},
    {"id":"A043","category":"academic","subcategory":"english","title":"英语六级（CET-6 ≥425分）","description":"通过大学英语六级考试","level":"国家级","score":10,"icon":"fa-language","section":"英语证书","note":"同一年过四六级可同时加分"},

    # --- (7) 考取证书 ---
    {"id":"A044","category":"academic","subcategory":"certificate","title":"专业技术等级证书（高级）","description":"获得专业技术等级证书高级","level":"国家级","score":7,"icon":"fa-certificate","section":"考取证书"},
    {"id":"A045","category":"academic","subcategory":"certificate","title":"专业技术等级证书（中级）","description":"获得专业技术等级证书中级","level":"国家级","score":5,"icon":"fa-certificate","section":"考取证书"},
    {"id":"A046","category":"academic","subcategory":"certificate","title":"专业技术等级证书（初级）","description":"获得专业技术等级证书初级","level":"国家级","score":3,"icon":"fa-certificate","section":"考取证书"},
    {"id":"A047","category":"academic","subcategory":"certificate","title":"计算机等级考试（四级）","description":"通过计算机四级考试","level":"国家级","score":5,"icon":"fa-laptop-code","section":"考取证书"},
    {"id":"A048","category":"academic","subcategory":"certificate","title":"计算机等级考试（三级）","description":"通过计算机三级考试","level":"国家级","score":4,"icon":"fa-laptop-code","section":"考取证书"},
    {"id":"A049","category":"academic","subcategory":"certificate","title":"计算机等级考试（二级）","description":"通过计算机二级考试","level":"国家级","score":3,"icon":"fa-laptop-code","section":"考取证书"},
    {"id":"A050","category":"academic","subcategory":"certificate","title":"计算机等级考试（一级）","description":"通过计算机一级考试","level":"国家级","score":2,"icon":"fa-laptop-code","section":"考取证书"},
    {"id":"A051","category":"academic","subcategory":"certificate","title":"普通话证书（二甲及以上）","description":"普通话水平测试二甲或以上","level":"国家级","score":5,"icon":"fa-microphone","section":"考取证书"},
    {"id":"A052","category":"academic","subcategory":"certificate","title":"普通话证书（二乙）","description":"普通话水平测试二乙","level":"国家级","score":3,"icon":"fa-microphone","section":"考取证书"},
    {"id":"A053","category":"academic","subcategory":"certificate","title":"普通话证书（三甲）","description":"普通话水平测试三甲","level":"国家级","score":1,"icon":"fa-microphone","section":"考取证书"},
    {"id":"A054","category":"academic","subcategory":"certificate","title":"修读双学位并获合格证书","description":"修读双学位并获得合格证书","level":"校级","score":10,"icon":"fa-graduation-cap","section":"考取证书"},
    {"id":"A055","category":"academic","subcategory":"certificate","title":"修读第二专业/辅修专业合格","description":"修读第二专业或辅修专业并获证书","level":"校级","score":8,"icon":"fa-graduation-cap","section":"考取证书"},
    {"id":"A056","category":"academic","subcategory":"certificate","title":"考取教育学/心理学证书（非师范）","description":"非师范专业考取教育学或心理学证书","level":"校级","score":2,"icon":"fa-book","section":"考取证书","note":"2分/项"},

    # --- (8) 学业成绩 ---
    {"id":"A057","category":"academic","subcategory":"grades","title":"必修课/限选课均分≥85分且单科≥75","description":"学年必修课和限选课平均成绩85分以上且单科75以上","level":"校级","score":5,"icon":"fa-chart-line","section":"学业成绩"},
    {"id":"A058","category":"academic","subcategory":"grades","title":"必修课/限选课均分≥80分且单科≥70","description":"学年成绩80分以上且单科70以上","level":"校级","score":3,"icon":"fa-chart-line","section":"学业成绩"},
    {"id":"A059","category":"academic","subcategory":"grades","title":"必修课/限选课均分≥75分且单科≥70","description":"学年成绩75分以上且单科70以上","level":"校级","score":2,"icon":"fa-chart-line","section":"学业成绩"},

    # --- (9) 考研 ---
    {"id":"A060","category":"academic","subcategory":"postgraduate","title":"参加研究生考试","description":"参加研究生考试（不含未考试者）","level":"校级","score":5,"icon":"fa-graduation-cap","section":"考研"},
    {"id":"A061","category":"academic","subcategory":"postgraduate","title":"成功考上研究生","description":"成功考上研究生","level":"校级","score":10,"icon":"fa-graduation-cap","section":"考研"},

    # --- (10) 学科相关重点学术成果 ---
    {"id":"A062","category":"academic","subcategory":"patent_copyright","title":"发表中科院二区及以上SCI论文","description":"以第一作者（或第二作者且第一作者为我院教师）发表SCI论文","level":"国家级","score":50,"icon":"fa-flask","section":"重点学术成果","note":"中科院二区及以上"},
    {"id":"A063","category":"academic","subcategory":"patent_copyright","title":"发表国内核心期刊/EI期刊/中科院二区以下SCI","description":"发表核心期刊或EI期刊论文","level":"国家级","score":40,"icon":"fa-flask","section":"重点学术成果"},
    {"id":"A064","category":"academic","subcategory":"patent_copyright","title":"技术博客获高点击量（1万+）","description":"在电子信息类博客发表原创技术文章获1万+点击或被推荐","level":"校级","score":10,"icon":"fa-blog","section":"重点学术成果"},
    {"id":"A065","category":"academic","subcategory":"patent_copyright","title":"授权发明专利（第一/第二作者）","description":"以第一作者或第二作者（第一作者为我院教师）获得发明专利授权","level":"国家级","score":40,"icon":"fa-lightbulb","section":"重点学术成果","note":"多人合作：前3名30%，其余10%"},
    {"id":"A066","category":"academic","subcategory":"patent_copyright","title":"授权实用新型专利","description":"获得实用新型专利授权","level":"国家级","score":20,"icon":"fa-lightbulb","section":"重点学术成果"},
    {"id":"A067","category":"academic","subcategory":"patent_copyright","title":"软件著作权","description":"获得软件著作权登记","level":"国家级","score":20,"icon":"fa-code","section":"重点学术成果"},
    {"id":"A068","category":"academic","subcategory":"patent_copyright","title":"授权外观专利","description":"获得外观专利授权","level":"国家级","score":10,"icon":"fa-paint-brush","section":"重点学术成果"},
    {"id":"A069","category":"academic","subcategory":"patent_copyright","title":"申请发明专利","description":"申请发明专利","level":"国家级","score":8,"icon":"fa-lightbulb","section":"重点学术成果","note":"申请阶段加分"},
    {"id":"A070","category":"academic","subcategory":"patent_copyright","title":"申请实用新型专利","description":"申请实用新型专利","level":"国家级","score":5,"icon":"fa-lightbulb","section":"重点学术成果","note":"申请阶段加分"},
    {"id":"A071","category":"academic","subcategory":"patent_copyright","title":"申请外观专利","description":"申请外观专利","level":"国家级","score":3,"icon":"fa-paint-brush","section":"重点学术成果","note":"申请阶段加分"},

    # ==================== 文体表现 (40分附加) ====================
    # --- 体育竞赛 ---
    {"id":"S001","category":"sports","subcategory":"sports_competition","title":"参加院运动会比赛","description":"参加院运动会比赛项目","level":"院级","score":2,"icon":"fa-running","section":"体育竞赛","note":"每次每项加2分"},
    {"id":"S002","category":"sports","subcategory":"sports_competition","title":"院运动会裁判员","description":"担任院运动会裁判员","level":"院级","score":2,"icon":"fa-whistle","section":"体育竞赛"},
    {"id":"S003","category":"sports","subcategory":"sports_competition","title":"院运动会第4-6名","description":"院运动会获得4-6名","level":"院级","score":2,"icon":"fa-medal","section":"体育竞赛","note":"每次每项另加"},
    {"id":"S004","category":"sports","subcategory":"sports_competition","title":"院运动会前3名","description":"院运动会获前三名（分别另加5/4/3分）","level":"院级","score":5,"icon":"fa-trophy","section":"体育竞赛","note":"第一名5，第二名4，第三名3"},
    {"id":"S005","category":"sports","subcategory":"sports_competition","title":"院运动会破院记录","description":"院运动会打破院记录","level":"院级","score":8,"icon":"fa-bolt","section":"体育竞赛"},
    {"id":"S006","category":"sports","subcategory":"sports_competition","title":"院级其他体育比赛（个人前三名）","description":"参加院级其它体育比赛获个人项目前三名","level":"院级","score":3,"icon":"fa-medal","section":"体育竞赛","note":"参赛+2，前三名另加3/2/1"},
    {"id":"S007","category":"sports","subcategory":"sports_competition","title":"参加校运动会比赛","description":"参加校运动会比赛项目","level":"校级","score":2,"icon":"fa-running","section":"体育竞赛","note":"每次每项加2分"},
    {"id":"S008","category":"sports","subcategory":"sports_competition","title":"校运动会裁判员","description":"担任校运动会裁判员","level":"校级","score":2,"icon":"fa-whistle","section":"体育竞赛"},
    {"id":"S009","category":"sports","subcategory":"sports_competition","title":"校运动会前3名","description":"校运动会获前三名","level":"校级","score":8,"icon":"fa-trophy","section":"体育竞赛","note":"每次每项另加8分"},
    {"id":"S010","category":"sports","subcategory":"sports_competition","title":"校运动会第4-8名","description":"校运动会获4-8名","level":"校级","score":4,"icon":"fa-medal","section":"体育竞赛","note":"每次每项另加4分"},
    {"id":"S011","category":"sports","subcategory":"sports_competition","title":"校运动会破校记录","description":"校运动会打破校记录","level":"校级","score":10,"icon":"fa-bolt","section":"体育竞赛"},
    {"id":"S012","category":"sports","subcategory":"sports_competition","title":"校级其他体育比赛个人前三名","description":"参加校级其它体育比赛获个人项目前三名","level":"校级","score":6,"icon":"fa-trophy","section":"体育竞赛","note":"前三名分别加6/4/2"},
    {"id":"S013","category":"sports","subcategory":"sports_competition","title":"参加省/市高校运动会","description":"参加省、市高校运动会","level":"省级","score":10,"icon":"fa-running","section":"体育竞赛","note":"每次每项加10分"},
    {"id":"S014","category":"sports","subcategory":"sports_competition","title":"省/市高校运动会获得名次","description":"省/市高校运动会获得名次","level":"省级","score":16,"icon":"fa-trophy","section":"体育竞赛","note":"按校级两倍加分"},
    {"id":"S015","category":"sports","subcategory":"sports_competition","title":"省/市高校运动会破记录","description":"省/市高校运动会破记录","level":"省级","score":16,"icon":"fa-bolt","section":"体育竞赛"},
    {"id":"S016","category":"sports","subcategory":"sports_competition","title":"参加全国运动会","description":"参加全国运动会比赛","level":"国家级","score":16,"icon":"fa-running","section":"体育竞赛","note":"每次每项加16分"},
    {"id":"S017","category":"sports","subcategory":"sports_competition","title":"全国运动会获得名次","description":"全国运动会获得名次","level":"国家级","score":24,"icon":"fa-trophy","section":"体育竞赛","note":"按校级三倍加分"},
    {"id":"S018","category":"sports","subcategory":"sports_competition","title":"全国运动会破记录","description":"全国运动会破记录","level":"国家级","score":32,"icon":"fa-bolt","section":"体育竞赛"},

    # --- 文艺演出 ---
    {"id":"S019","category":"sports","subcategory":"arts_performance","title":"院级文艺演出节目获奖参加者（特等奖）","description":"参加院级文艺演出节目获特等奖","level":"院级","score":5,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S020","category":"sports","subcategory":"arts_performance","title":"院级文艺演出节目获奖参加者（一等奖）","description":"参加院级文艺演出节目获一等奖","level":"院级","score":4,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S021","category":"sports","subcategory":"arts_performance","title":"院级文艺演出节目获奖参加者（二等奖）","description":"参加院级文艺演出节目获二等奖","level":"院级","score":3,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S022","category":"sports","subcategory":"arts_performance","title":"院级文艺演出节目获奖参加者（三等奖）","description":"参加院级文艺演出节目获三等奖","level":"院级","score":2,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S023","category":"sports","subcategory":"arts_performance","title":"校级文艺演出节目获奖参加者（特等奖）","description":"参加校级文艺演出节目获特等奖","level":"校级","score":10,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S024","category":"sports","subcategory":"arts_performance","title":"校级文艺演出节目获奖参加者（一等奖）","description":"参加校级文艺演出节目获一等奖","level":"校级","score":8,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S025","category":"sports","subcategory":"arts_performance","title":"校级文艺演出节目获奖参加者（二等奖）","description":"参加校级文艺演出节目获二等奖","level":"校级","score":6,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S026","category":"sports","subcategory":"arts_performance","title":"校级文艺演出节目获奖参加者（三等奖）","description":"参加校级文艺演出节目获三等奖","level":"校级","score":4,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S027","category":"sports","subcategory":"arts_performance","title":"校级文艺演出节目获奖参加者（表扬奖）","description":"参加校级文艺演出节目获表扬奖","level":"校级","score":2,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S028","category":"sports","subcategory":"arts_performance","title":"省级/高校文艺演出节目获奖（特等奖）","description":"参加省级或高校文艺演出获特等奖","level":"省级","score":12,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S029","category":"sports","subcategory":"arts_performance","title":"省级/高校文艺演出节目获奖（一等奖）","description":"参加省级或高校文艺演出获一等奖","level":"省级","score":10,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S030","category":"sports","subcategory":"arts_performance","title":"省级/高校文艺演出节目获奖（二等奖）","description":"参加省级或高校文艺演出获二等奖","level":"省级","score":8,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S031","category":"sports","subcategory":"arts_performance","title":"省级/高校文艺演出节目获奖（三等奖）","description":"参加省级或高校文艺演出获三等奖","level":"省级","score":6,"icon":"fa-theater-masks","section":"文艺演出"},
    {"id":"S032","category":"sports","subcategory":"arts_performance","title":"省级/高校文艺演出节目获奖（表扬奖）","description":"参加省级或高校文艺演出获表扬奖","level":"省级","score":4,"icon":"fa-theater-masks","section":"文艺演出"},

    # --- 社团竞赛（文体类） ---
    {"id":"S033","category":"sports","subcategory":"club_competition","title":"社团举办竞赛获奖（第一名）","description":"参加社团举办的竞赛获第一名","level":"院级","score":4,"icon":"fa-trophy","section":"社团竞赛"},
    {"id":"S034","category":"sports","subcategory":"club_competition","title":"社团举办竞赛获奖（第二名）","description":"参加社团举办的竞赛获第二名","level":"院级","score":3,"icon":"fa-medal","section":"社团竞赛"},
    {"id":"S035","category":"sports","subcategory":"club_competition","title":"社团举办竞赛获奖（第三名）","description":"参加社团举办的竞赛获第三名","level":"院级","score":2,"icon":"fa-medal","section":"社团竞赛"},
    {"id":"S036","category":"sports","subcategory":"club_competition","title":"社团举办竞赛获奖（其他）","description":"参加社团举办的竞赛获其他名次","level":"院级","score":1,"icon":"fa-award","section":"社团竞赛"},

    # 非专业竞赛（文体类-from学业表3）
    {"id":"S037","category":"sports","subcategory":"other_competition","title":"非专业竞赛（国家级一等奖）","description":"演讲/辩论/征文等非专业竞赛国家级一等奖","level":"国家级","score":15,"icon":"fa-trophy","section":"非专业竞赛"},
    {"id":"S038","category":"sports","subcategory":"other_competition","title":"非专业竞赛（国家级二等奖）","description":"国家级二等奖","level":"国家级","score":12,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S039","category":"sports","subcategory":"other_competition","title":"非专业竞赛（国家级三等奖）","description":"国家级三等奖","level":"国家级","score":10,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S040","category":"sports","subcategory":"other_competition","title":"非专业竞赛（国家级其他奖）","description":"国家级其他奖项","level":"国家级","score":6,"icon":"fa-award","section":"非专业竞赛"},
    {"id":"S041","category":"sports","subcategory":"other_competition","title":"非专业竞赛（省级一等奖）","description":"省级一等奖或特等奖","level":"省级","score":10,"icon":"fa-trophy","section":"非专业竞赛"},
    {"id":"S042","category":"sports","subcategory":"other_competition","title":"非专业竞赛（省级二等奖）","description":"省级二等奖","level":"省级","score":8,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S043","category":"sports","subcategory":"other_competition","title":"非专业竞赛（省级三等奖）","description":"省级三等奖","level":"省级","score":6,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S044","category":"sports","subcategory":"other_competition","title":"非专业竞赛（省级其他奖）","description":"省级其他奖项","level":"省级","score":4,"icon":"fa-award","section":"非专业竞赛"},
    {"id":"S045","category":"sports","subcategory":"other_competition","title":"非专业竞赛（校级一等奖）","description":"校级一等奖或特等奖","level":"校级","score":5,"icon":"fa-trophy","section":"非专业竞赛"},
    {"id":"S046","category":"sports","subcategory":"other_competition","title":"非专业竞赛（校级二等奖）","description":"校级二等奖","level":"校级","score":4,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S047","category":"sports","subcategory":"other_competition","title":"非专业竞赛（校级三等奖）","description":"校级三等奖","level":"校级","score":3,"icon":"fa-medal","section":"非专业竞赛"},
    {"id":"S048","category":"sports","subcategory":"other_competition","title":"非专业竞赛（校级其他奖/参赛）","description":"校级其他奖项或参赛","level":"校级","score":2,"icon":"fa-award","section":"非专业竞赛"},
    {"id":"S049","category":"sports","subcategory":"other_competition","title":"全国大学生英语竞赛参赛","description":"参加全国大学生英语竞赛（初赛/复赛/决赛）","level":"校级","score":1,"icon":"fa-language","section":"非专业竞赛","note":"参赛每次加1分；获奖按条例加分，属于文体类"},

    # 获奖通用（文体all levels）
    {"id":"S050","category":"sports","subcategory":"sports_competition","title":"体育竞赛（院级第一名）","description":"院级体育竞赛第一名","level":"院级","score":4,"icon":"fa-medal","section":"体育竞赛"},
    {"id":"S051","category":"sports","subcategory":"sports_competition","title":"体育竞赛（校级第一名）","description":"校级体育竞赛第一名","level":"校级","score":5,"icon":"fa-medal","section":"体育竞赛"},
    {"id":"S052","category":"sports","subcategory":"sports_competition","title":"体育竞赛（市高校/省级第一名）","description":"市高校或省级体育竞赛第一名","level":"省级","score":10,"icon":"fa-trophy","section":"体育竞赛"},
    {"id":"S053","category":"sports","subcategory":"sports_competition","title":"体育竞赛（全国性第一名）","description":"全国性体育竞赛第一名","level":"国家级","score":15,"icon":"fa-trophy","section":"体育竞赛"},
]

# 类别映射
CAT_INFO = {
    'moral': {'name': '品德行为表现', 'icon': 'fa-heart', 'color': '#1a4d7e', 'bg': '#edf2f7', 'base': 70, 'extra_max': 30},
    'academic': {'name': '学业表现', 'icon': 'fa-book-open', 'color': '#2980b9', 'bg': '#e3edf7', 'base': 80, 'extra_max': 20},
    'sports': {'name': '文体表现', 'icon': 'fa-trophy', 'color': '#c98d1a', 'bg': '#fef9ee', 'base': 60, 'extra_max': 40},
}

SUBCAT_NAMES = {
    'student_cadre': '学生干部', 'publication': '发表文章', 'activity': '参加活动',
    'volunteer': '志愿活动', 'honor': '荣誉称号', 'good_deed': '好人好事',
    'dormitory': '文明宿舍', 'organize': '承办活动', 'duty': '值班',
    'congress': '代表大会', 'class_award': '班集体获奖',
    'paper': '学术论文', 'key_competition': '重点科技竞赛', 'innovation_project': '科研立项',
    'other_competition': '其他竞赛', 'english': '英语证书', 'certificate': '考取证书',
    'grades': '学业成绩', 'postgraduate': '考研', 'patent_copyright': '专利/软著/学术成果',
    'sports_competition': '体育竞赛', 'arts_performance': '文艺演出', 'club_competition': '社团竞赛',
}

LEVEL_ORDER = {'国家级': 4, '省级': 3, '校级': 2, '院级': 1, '班级': 0}

# 证明材料要求：每个子类需要提交的证明材料类型
REQUIRED_PROOFS = {
    'student_cadre': [
        {'type': 'appointment', 'name': '任职证明/聘书', 'description': '学校/学院出具的正式任职文件或聘书，需有盖章和任期说明'},
    ],
    'honor': [
        {'type': 'certificate', 'name': '荣誉证书', 'description': '相关荣誉称号的证书或表彰文件清晰照片/扫描件'},
    ],
    'good_deed': [
        {'type': 'certificate', 'name': '献血证/表彰证明', 'description': '献血证、见义勇为证明或相关表彰文件'},
    ],
    'dormitory': [
        {'type': 'certificate', 'name': '文明宿舍证明', 'description': '学校/学院出具的文明宿舍评优文件或表彰通知'},
    ],
    'volunteer': [
        {'type': 'certificate', 'name': '志愿活动证明', 'description': '志愿服务时长证明、活动组织方出具的证明文件'},
    ],
    'activity': [
        {'type': 'certificate', 'name': '活动参与证明', 'description': '参加活动的证明文件或活动组织方出具的参与证明'},
    ],
    'organize': [
        {'type': 'certificate', 'name': '活动承办证明', 'description': '承办活动的相关证明文件'},
    ],
    'duty': [
        {'type': 'certificate', 'name': '值班/考勤证明', 'description': '值班或相关工作的出勤记录'},
    ],
    'congress': [
        {'type': 'certificate', 'name': '代表大会参与证明', 'description': '参加代表大会的证明文件'},
    ],
    'class_award': [
        {'type': 'certificate', 'name': '班集体获奖证明', 'description': '班集体获奖的表彰文件'},
    ],
    'paper': [
        {'type': 'paper_publish', 'name': '论文发表证明', 'description': '期刊录用通知或论文发表页面截图/扫描件'},
        {'type': 'paper_content', 'name': '论文全文', 'description': '论文全文PDF文件'},
    ],
    'key_competition': [
        {'type': 'award_cert', 'name': '获奖证书', 'description': '竞赛获奖证书的清晰照片或扫描件'},
        {'type': 'participation', 'name': '参赛证明', 'description': '参赛报名记录或参赛证明文件（如有）'},
    ],
    'innovation_project': [
        {'type': 'project_doc', 'name': '立项/结项证明', 'description': '项目立项通知、合同或结项证明文件'},
        {'type': 'project_result', 'name': '项目成果证明', 'description': '项目相关成果材料（报告、论文、作品等）'},
    ],
    'patent_copyright': [
        {'type': 'patent_cert', 'name': '专利/软著证书', 'description': '专利授权证书、软件著作权登记证书的清晰扫描件'},
    ],
    'english': [
        {'type': 'score_report', 'name': '成绩单/证书', 'description': '英语四六级考试成绩单或证书的清晰照片/扫描件'},
    ],
    'certificate': [
        {'type': 'cert_file', 'name': '等级证书/成绩单', 'description': '计算机等级证书、普通话等级证书或成绩单的清晰照片/扫描件'},
    ],
    'grades': [
        {'type': 'transcript', 'name': '成绩单', 'description': '教务处出具的正式成绩单'},
    ],
    'postgraduate': [
        {'type': 'admission', 'name': '录取证明', 'description': '研究生录取通知书或调档函'},
    ],
    'publication': [
        {'type': 'article', 'name': '发表文章证明', 'description': '发表文章的刊物截图或录用证明'},
    ],
    'other_competition': [
        {'type': 'award_cert', 'name': '获奖证书', 'description': '竞赛获奖证书或参赛证明的清晰照片/扫描件'},
    ],
    'sports_competition': [
        {'type': 'award_cert', 'name': '获奖证书/参赛证明', 'description': '体育竞赛获奖证书或参赛证明'},
    ],
    'arts_performance': [
        {'type': 'award_cert', 'name': '演出/获奖证明', 'description': '文艺演出的参与证明或获奖证书'},
    ],
    'club_competition': [
        {'type': 'award_cert', 'name': '社团竞赛获奖证明', 'description': '社团竞赛的获奖证书或证明文件'},
    ],
}


def get_required_proofs(item: dict) -> list:
    """获取某个综测项目需要提交的证明材料清单"""
    subcat = item.get('subcategory', '')
    return REQUIRED_PROOFS.get(subcat, [
        {'type': 'general', 'name': '相关证明材料', 'description': '请上传能证明该项成果的对应材料文件'}
    ])


def get_all_subcat_names() -> dict:
    """获取所有子类名称映射"""
    return SUBCAT_NAMES
