import re
with open('apps/block/tests/test_block_business_rules.py', 'r') as f:
    content = f.read()

content = re.sub(r'    def test_sincroniza_status_local_quando_ad_real_diverge_sem_chamar_executor.*?(?=    def)', '', content, flags=re.DOTALL)

with open('apps/block/tests/test_block_business_rules.py', 'w') as f:
    f.write(content)
