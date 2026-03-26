# 调用工具格式定义
func_sword_of_light = {
        'name': 'sword_of_light',
        'description': '使用电磁炮“光之剑”发起攻击',
        'parameters': {
            'type': 'object',
            'properties': {
                'target': {
                    'type': 'string',
                    'description':
                    '攻击目标的名字',
                },
            },
            'required': ['target'],
        },
    }
func_move_random = {
        'name': 'move',
        'description': '离开当前场景，前往其他地点',
        'parameters': {
            'type': 'object',
            'properties': {
                'to': {
                    'type': 'string',
                    'description':
                    '接下来要前往的场景或地点的名称',
                },
            },
            'required': ['to'],
        },
    }
func_search_for_item = {
        'name': 'search_for_item',
        'description': '道具搜索',
        'parameters': {
            'type': 'object',
            'properties': {
                'object': {
                    'type': 'string',
                    'description':
                    '指定具体的搜索对象，例如宝箱、房屋、垃圾箱等',
                },
            },
            'required': ['object'],
        },
    }
func_search_on_internet = {
        'name': 'search_on_internet',
        'description': '上网搜索、查找相关信息',
        'parameters': {
            'type': 'query',
            'properties': {
                'query': {
                    'type': 'string',
                    'description':
                    '需要查找信息的条目',
                },
            },
            'required': ['query'],
        },
    }
func_move = {
        'name': 'move',
        'description': '出发前往其他地点（步行）',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的地点选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_decide_area = {
        'name': 'decide_area',
        'description': '决定前往哪个区域',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的区域选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_decide_school = {
        'name': 'decide_school',
        'description': '决定前往哪个校区',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '可以前往的校区选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_railway = {
        'name': 'take_railway',
        'description': '搭乘列车，出发前往其他站点',
        'parameters': {
            'type': 'object',
            'properties': {
                'options': {
                    'type': 'string',
                    'description':
                    '通过列车轨道可以直达的地点选项：\n'
                    '{OPTIONS}',
                },
            },
            'required': ['options'],
        },
    }
func_walk = {
        'name': 'walk',
        'description': '在当前场景内走动（改变位置）',
        'parameters': {
            'type': 'object',
            'properties': {
                'to': {
                    'type': 'string',
                    'description':
                    '行动至某个位置，用一个数字表示（取值范围在0-{SIZE}之间）',
                },
            },
            'required': ['to'],
        },
    }