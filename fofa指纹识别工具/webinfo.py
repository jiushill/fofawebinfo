import json
import os
import re
import requests
import warnings
import optparse
import time
import csv
import chardet
from multiprocessing import Pool,Process
warnings.filterwarnings('ignore')

process=50
proxies={}
headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
         "Cookie":"a=1;rememberMe=xxx"}
fingerprintlist={}
teample=[]
cmsdata=[] #主动检测
save="" # 保存文件格式
savefilename = str(time.strftime("%Y-%m-%d", time.localtime())) # 保存的文件名
savelist=["txt","csv","json"] # 支持的保存文件格式

# 遍历fofa指纹库
def getfingerprint():
    data=os.walk(os.path.join("rules","fofa"))
    for d,_,file in data:
        for f in file:
            fname=f.split(".json")[0]
            filepath=os.path.join(d,f)
            if len(teample)==0:
                getfin=open(filepath,"r",encoding="utf-8").read()
                fingerprintlist[fname]=json.loads(getfin)
            else:
                if fname in teample:
                    getfin = open(filepath, "r", encoding="utf-8").read()
                    fingerprintlist[fname] = json.loads(getfin)

# 获取请求response
    # 获取的内容有
        # url - 请求的url
        # body - 返回主体
        # title - 标题
        # httpcode - 状态码
        # headers - 响用头部
def gethttpinfo(url):
    info={}
    try:
        rqt=requests.get(url=url,headers=headers,proxies=proxies,verify=False,timeout=5)
        content=rqt.content
        enc=chardet.detect(content)["encoding"]
        if enc==None:
            encode="utf-8"
        else:
            encode=enc
        text=content.decode(encode) # 处理title乱码
        title_search=re.findall("title([\s\S]*?)</title>",text)
        if len(title_search)==0:
            title=""
        else:
            title=title_search[0].replace("title>","").replace("</","").replace("\r","").replace("\n","").lstrip(">")
        httpcode=rqt.status_code
        responseheader=""
        for key in rqt.headers.keys():
            responseheader += "{}: {}\n".format(key, rqt.headers[key])
        info["url"]=url
        info["body"]=rqt.text
        info["title"]=title
        info["httpcode"]=httpcode
        info["headers"]=responseheader
        return info
    except Exception as error:
        print("[ERROR] URL:{} error:{}".format(url,error))
        return ""

# 解析返回内容判断是那个指纹
def Parsing(response,fingerprintlist):
        result=[]
        start=0
        end=len(fingerprintlist)
        for keyname in fingerprintlist:
            #print(response)
            regexpid = []
            jsondata = fingerprintlist[keyname]  # json数据获取
           # print(jsondata)
            matches = jsondata["matches"]
            matchescount = len(matches)  # 匹配类型数量
            webname = jsondata["name"]  # web指纹名称
            #print(webname, matchescount, condition)
            if "condition" in jsondata.keys():
                condition = jsondata["condition"]  # 是否有特殊条件
            else:
                condition = "None"

            for id, match in enumerate(matches):
                searchkeylist = list(match.keys())
                searchtype = match[searchkeylist[0]]  # 从什么地方搜索获取
                searchmatch = searchkeylist[1]  # 搜索类型 (text|regexp)
                search = match[searchkeylist[1]]  # 搜索的内容
                if searchtype in response.keys():
                    #print(searchtype,searchmatch,search)
                    if searchmatch=="text":
                        msearch=response[searchtype] # 取对应的数据
                        if search in msearch:
                            regexpid.append(id)
                    elif searchmatch=="regexp":
                        msearch=response[searchtype]
                        find=re.findall(search,msearch)
                        if len(find)>0:
                            regexpid.append(id)

                # condition处理
                res = []
               # res.append(response)
                if len(regexpid) > 0:
                    if [webname] in result:
                        break
                    if condition=="None":
                        res.append(webname)
                        #print("Found webname:{}".format(webname))
                   #    print(res)
                    else:
                        tx = re.findall("[0-9]", condition)
                        for v in tx:
                            condition = condition.replace(v, "{} in regexpid".format(v))
                        string = "if {}:res.append(webname)".format(condition)
                        exec(string)

                start+=1
                if len(res)>0:
                    result.append(res)

        result.append(response)

        return result


# 保存文件
def savetofile(jgdata):
    if save=="txt":
        for key in jgdata:
            print("url:{} code:{} title:{} bodylength:{} webname:{}".format(jgdata[key]["url"],jgdata[key]["code"],jgdata[key]["title"],jgdata[key]["bodylength"],jgdata[key]["webname"]),file=open("{}.txt".format(savefilename),"a",encoding="utf-8"))
    elif save=="csv":
        with open("{}.{}".format(savefilename,save),"w",encoding="utf-8",newline="") as csvfile:
            writer=csv.writer(csvfile)
            writer.writerow(["url","code","title","bodylength","webname"])
            for key in jgdata:
                writer.writerow([jgdata[key]["url"],jgdata[key]["code"],jgdata[key]["title"],jgdata[key]["bodylength"],jgdata[key]["webname"]])

    elif save=="json":
        out="["
        for key in jgdata:
            out+=json.dumps(jgdata[key]) + ","
        out=out.rstrip(",")
        out+="]"
        with open("{}.{}".format(savefilename,save),"w",encoding="utf-8") as savejson:
            savejson.write(out)

# 帮助输出
def helpprint():
    usage="\nExample\npython webinfo.py -u <url> [option]\n" \
          "python webinfo.py -u <url> -t <teample> [option]\n" \
          "python webinfo.py -f <file> [option]\n" \
          "python webinfo.py -f <file> -t <teample> [option]\n"

    example="python webinfo.py -u http://127.0.0.1 #全部模板检测\n" \
            "python webinfo.py -u http://127.0.0.1 -t zabbix,weblogic #指定检测zabbix和weblogic模板\n" \
            "python webinfo.py -u http://127.0.0.1 -p socks5://127.0.0.1:1118 #指定代理\n" \
            "python webinfo.py -u http://127.0.0.1 -s txt #保存文件\n"
    print(usage)
    print(example)

# 列出支持的指纹
def rulesprint():
    getfingerprint()
    print("指纹库总数量:{}".format(len(list(fingerprintlist.keys()))))
    for id,rulename in enumerate(fingerprintlist.keys()):
        print(id,rulename)

# 主函数，用于各个函数调度
def main(urlist,teample_=""):
    # 模板是否有设置
    print("代理:{}".format(proxies))
    if teample_!=None:
        if "," in teample_:
            for tname in teample_.split(","):
                teample.append(tname)
        else:
            teample.append(teample_)

        print("teample:{}".format(teample))
    else:
        print("teample:ALL")

    print("进程数量:{}".format(process))
    print("保存文件格式:{}".format(save))
    print("Start time:{}".format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
    result=[]
    webinfo=[]
    P=Pool(processes=process)
    T=Pool(processes=process)
    getfingerprint()
    for url in urlist:
        result.append(P.apply_async(gethttpinfo,args=(url,))) # 发出请求
    P.close()
    P.join()

    # 异步多进程匹配指纹
    for httpinfo in result:
        response=httpinfo.get()

        if response!="":
            #print("check url:{}".format(response["url"]))
            webinfo.append(T.apply_async(Parsing,args=(response,fingerprintlist)))
    T.close()
    T.join()

    jgdata={}

    for data in webinfo:
        infodata = {}
        jg=data.get()
        if jg!=None:
            url=jg[-1]["url"]
            httpcode=jg[-1]["httpcode"]
            title=jg[-1]["title"]
            bodylength=len(jg[-1]["body"])
            infodata["url"]=url
            infodata["code"]=httpcode
            infodata["title"]=str(title).replace("<title>","").replace("</title>","")
            infodata["bodylength"]=bodylength
            infodata["webname"]="|".join(["".join(webname) for webname in jg[0:-1]])
            jgdata[url]=infodata
           # print(url,webname,httpcode,title,bodylength)

    for key in jgdata:
        print("url:{} code:{} title:{} bodylength:{} webname:{}".format(jgdata[key]["url"],jgdata[key]["code"],jgdata[key]["title"],jgdata[key]["bodylength"],jgdata[key]["webname"]))
        if save!=None and save!="":
            savetofile(jgdata)
    
    if save != None and save != "":
        print("save file:{}.{}".format(savefilename,save))

    print("End time:{}".format(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))


if __name__ == '__main__':
    parser=optparse.OptionParser()
    parser.add_option("-u",dest="url",help="单独url检测")
    parser.add_option("-f",dest="file",help="批量检测")
    parser.add_option("-t",dest="teample",help="指定模板检测,批量模板检测")
    parser.add_option("-s",dest="save",help="保存文件类型:txt|csv|json")
    parser.add_option("-i",dest="process",help="进程数量(default:50)")
    parser.add_option("-l",dest="getrules",action="store_true",help="列出支持的指纹")
    parser.add_option("-p",dest="proxy",help="指定代理,Example:http://127.0.0.1:8080 | socks5://127.0.0.1:1080")
    option,args=parser.parse_args()
    if option.getrules:
        rulesprint()
        exit()

    if option.process:
        try:
            process=int(option.process)
        except:
            print("[-] 进程数量不为数字")
    if option.proxy:
        if option.proxy!=None:
            proxy=option.proxy.split("://")
            proxies[proxy[0]]=option.proxy
    if option.save:
        save=option.save
        if save not in savelist:
            print("[-] 没有保存的文件格式，支持的格式:{}".format(",".join(savelist)))
            exit()

    if option.url or (option.url and option.teample):
        if option.teample!="":
            tpe=option.teample
        else:
            tpe=""
        main([option.url],tpe)
    elif option.file or (option.file and option.teample):
        if os.path.exists(option.file):
            urllist=open(option.file,"r",encoding="utf-8").read().split("\n")
            if option.teample != "":
                tpe = option.teample
            else:
                tpe = ""
            main(urllist,tpe)
        else:
            print("[-] 文件不存在:{}".format(option.file))
    else:
        parser.print_help()
        helpprint()
