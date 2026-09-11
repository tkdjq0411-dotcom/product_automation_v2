import ast,json,re,unittest
from pathlib import Path
from typing import Any
source=Path(__file__).parents[2]/'app/modules/sourcing/browser_capture.py'
tree=ast.parse(source.read_text())
names={'_clean_text','_normalize_variants'}
ns={'Any':Any,'json':json,'re':re}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),str(source),'exec'),ns)
class Regression(unittest.TestCase):
 def test_negative_and_full_paths(self):
  rows=[{'options':[{'name':'parent','value':str(i)},{'name':'leaf','value':'실버'}],'additional_price':-1000} for i in range(10001)]
  result=ns['_normalize_variants'](rows+rows[:1])
  self.assertEqual(len(result),10001)
  self.assertEqual(result[-1]['additional_price'],-1000)
if __name__=='__main__':unittest.main()
