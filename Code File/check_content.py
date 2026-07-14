with open('blocked_page.html', 'r', encoding='utf-8') as f:
    text = f.read()
print("Length of file:", len(text))
for keyword in ['Systemet', 'foretage', 'indlæser', 'cannot', 'perform', 'try again', 'robot', 'captcha', 'recaptcha', 'gs_alrt', 'gs_top', 'gs_res_ccl']:
    print(f"'{keyword}' in file:", keyword.lower() in text.lower())
