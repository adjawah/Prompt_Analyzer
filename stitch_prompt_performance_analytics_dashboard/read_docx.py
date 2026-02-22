import zipfile
import xml.etree.ElementTree as ET
import sys

def read_docx(docx_path):
    try:
        with zipfile.ZipFile(docx_path, 'r') as z:
            xml_content = z.read('word/document.xml')
        
        tree = ET.fromstring(xml_content)
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = []
        for paragraph in tree.findall('.//w:p', namespaces):
            para_text = "".join([node.text for node in paragraph.findall('.//w:t', namespaces) if node.text])
            if para_text:
                text.append(para_text)

        print("\n".join(text))
    except Exception as e:
        print(f"Error reading docx: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
         read_docx(sys.argv[1])
    else:
         print("Please provide a path to a docx file.")
