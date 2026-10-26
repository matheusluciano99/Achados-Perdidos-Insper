from io import BytesIO

from PIL import Image


def imagem_teste(formato="PNG", tamanho=(12, 8), exif=None):
    arquivo = BytesIO()
    imagem = Image.new("RGB", tamanho, color="blue")
    imagem.save(arquivo, format=formato, **({"exif": exif} if exif else {}))
    return arquivo.getvalue()


def foto_upload(conteudo=None):
    return {"foto": ("foto.png", imagem_teste() if conteudo is None else conteudo, "image/png")}
