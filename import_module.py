import importlib

def load_module(module_name):
    """ 주어진 모듈 이름으로 모듈을 동적으로 불러온다. """
    module = importlib.import_module(module_name)
    module.load_page()
