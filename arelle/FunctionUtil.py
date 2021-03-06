'''
Created on Dec 31, 2010

@author: Mark V Systems Limited
(c) Copyright 2010 Mark V Systems Limited, All rights reserved.
'''
import xml.dom, datetime
from arelle import (ModelValue,  ModelObject, XmlUtil)
from arelle.XPathContext import (XPathException, FunctionArgType)

def anytypeArg(xc, args, i, type, missingArgFallback=None):
    if len(args) > i:
        item = args[i]
    else:
        item = missingArgFallback
    if hasattr(item, "__iter__") and not isinstance(item, str):
        if len(item) > 1: raise FunctionArgType(i,type)
        if len(item) == 0: return ()
        item = item[0]
    if isinstance(item, ModelObject.ModelObject) and not type.startswith("arelle:Model"): 
        item = item.element
    return item
    
def atomicArg(xc, p, args, i, type, missingArgFallback=None, emptyFallback=()):
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == (): return emptyFallback
    return xc.atomize(p, item)

def stringArg(xc, args, i, type, missingArgFallback=None, emptyFallback=''):
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == (): return emptyFallback
    if isinstance(item, xml.dom.Node):
        if item.nodeType == xml.dom.Node.ELEMENT_NODE:
            return XmlUtil.text(item)
        elif item.nodeType == xml.dom.Node.ATTRIBUTE_NODE:
            return item.value
        else:
            return ""
    return str(item)

def numericArg(xc, p, args, i=0, missingArgFallback=None, emptyFallback=0, convertFallback=None):
    item = anytypeArg(xc, args, i, "numeric?", missingArgFallback)
    if item == (): return emptyFallback
    numeric = xc.atomize(p, item)
    if not isinstance(numeric,(int,float)): 
        if convertFallback is None:
            raise FunctionArgType(i,"numeric?")
        try:
            numeric = float(numeric)
        except ValueError:
            numeric = convertFallback
    return numeric

def qnameArg(xc, p, args, i, type, missingArgFallback=None, emptyFallback=()):
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == (): return emptyFallback
    qn = xc.atomize(p, item)
    if not isinstance(qn, ModelValue.QName): raise FunctionArgType(i,type)
    return qn

def nodeArg(xc, args, i, type, missingArgFallback=None, emptyFallback=None):
    item = anytypeArg(xc, args, i, type, missingArgFallback)
    if item == (): return emptyFallback
    if not isinstance(item, xml.dom.Node): raise FunctionArgType(i,type)
    return item

def testTypeCompatiblity(xc, p, op, a1, a2):
    if (isinstance(a1,ModelValue.DateTime) and isinstance(a2,ModelValue.DateTime)):
        if a1.dateOnly == a2.dateOnly:
            return # can't interoperate between date and datetime
    elif ((type(a1) == type(a2)) or
        ((isinstance(a1,int) or isinstance(a1,float)) and 
         (isinstance(a2,int) or isinstance(a2,float)))):
        return
    elif op in ('+','-'):
        if ((isinstance(a1,ModelValue.DateTime) and isinstance(a2,(ModelValue.YearMonthDuration,datetime.timedelta))) or
            ((isinstance(a1,datetime.date) and isinstance(a2,datetime.timedelta)))):
            return
    else:
        if (isinstance(a1,datetime.date) and isinstance(a2,datetime.date)):
            return
    raise XPathException(p, 'err:XPTY0004', _('Value operation {0} incompatible arguments {1} and {2}').format(op,a1,a2))
