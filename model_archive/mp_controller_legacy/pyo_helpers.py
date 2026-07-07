import pyomo.environ as pyo

def set_block_attribute_by_name(model, block_name, attr_name, value):
    pyo_comp = model.find_component(block_name)
    setattr(pyo_comp, attr_name, value)

def set_indexed_block_attribute_by_name(model, block_name, attr_name, values, index=None):
    if not index:
        index = range(len(values))
    pyo_comp = model.find_component(block_name)
    attr = getattr(pyo_comp, attr_name)
    for i in index:
        attr[i] = values[i]

def get_block_attribute_by_name(model, block_name, attr_name):
    pyo_comp = model.find_component(block_name)
    return pyo.value(getattr(pyo_comp, attr_name))

def get_indexed_block_attribute_by_name(model, block_name, attr_name, index):
    pyo_comp = model.find_component(block_name)
    return pyo.value(getattr(pyo_comp, attr_name)[index])

def get_all_indexed_block_attributes_by_name(model, block_name, attr_name):
    pyo_comp = model.find_component(block_name)
    return pyo.value(getattr(pyo_comp, attr_name)[:])
