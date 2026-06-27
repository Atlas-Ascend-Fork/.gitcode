import yaml
import sys

def read_yaml(files):
    with open(files) as file:
        data = yaml.load(file, Loader=yaml.FullLoader)
        return data
def main():
    markdown_filter_file = sys.argv[1]
    branch = sys.argv[2]
    ss = read_yaml(markdown_filter_file)
    filter_dic = ss.get("filter", {})
    # 判断字典为空
    if not filter_dic:
        return {}
    branch_filter = filter_dic.get(branch, [])
    print(' '.join(branch_filter))

main()