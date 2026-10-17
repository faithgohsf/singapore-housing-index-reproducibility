from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import retrieve_public_data as module

def test_nested_mendeley_download_url(monkeypatch,tmp_path):
 calls=[]
 class Response:
  headers={}
  def raise_for_status(self):pass
  def json(self):return [{'filename':'data in brief.csv','content_details':{'download_url':'https://example.org/actual-download'}}]
  def iter_content(self,*args):yield b'a,b\n1,2\n'
 def get(url,**kw):calls.append(url);return Response()
 monkeypatch.setattr(module.requests,'get',get)
 monkeypatch.setattr(module,'validate_csv_snapshot',lambda *a,**kw:1)
 module._download_mendeley(tmp_path/'test.csv')
 assert calls[1]=='https://example.org/actual-download'
