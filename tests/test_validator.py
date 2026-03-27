"""Testes para o modulo de validacao."""

from datetime import datetime, timezone
from decimal import Decimal

from leilao_inteligente.pipeline.validator import normalizar_dados, validar_lote


class TestNormalizarDados:
    def test_normaliza_preco_string_brasileiro(self):
        dados = {"preco_lance": "R$ 3.500,00"}
        resultado = normalizar_dados(dados)
        assert resultado["preco_lance"] == Decimal("3500.00")

    def test_normaliza_preco_numerico(self):
        dados = {"preco_lance": 3290.00}
        resultado = normalizar_dados(dados)
        assert resultado["preco_lance"] == 3290.00

    def test_normaliza_sexo_com_acento(self):
        dados = {"sexo": "Fêmea"}
        resultado = normalizar_dados(dados)
        assert resultado["sexo"] == "femea"

    def test_normaliza_sexo_plural(self):
        dados = {"sexo": "Machos"}
        resultado = normalizar_dados(dados)
        assert resultado["sexo"] == "macho"

    def test_normaliza_estado_minusculo(self):
        dados = {"local_estado": "go"}
        resultado = normalizar_dados(dados)
        assert resultado["local_estado"] == "GO"

    def test_normaliza_raca_com_espacos(self):
        dados = {"raca": "  nelore  "}
        resultado = normalizar_dados(dados)
        assert resultado["raca"] == "Nelore"

    def test_normaliza_cidade_com_espacos(self):
        dados = {"local_cidade": "  araçatuba  "}
        resultado = normalizar_dados(dados)
        assert resultado["local_cidade"] == "Araçatuba"

    def test_normaliza_pelagem_maiuscula(self):
        dados = {"pelagem": "  Branco  "}
        resultado = normalizar_dados(dados)
        assert resultado["pelagem"] == "branco"

    def test_normaliza_lote_numero_int_para_str(self):
        dados = {"lote_numero": 5}
        resultado = normalizar_dados(dados)
        assert resultado["lote_numero"] == "5"

    def test_normaliza_lote_numero_alfanumerico(self):
        dados = {"lote_numero": "001A"}
        resultado = normalizar_dados(dados)
        assert resultado["lote_numero"] == "001A"

    def test_normaliza_fazenda_remove_recinto(self):
        dados = {"fazenda_vendedor": "Recinto FAZ. SANTO ANTONIO"}
        resultado = normalizar_dados(dados)
        assert resultado["fazenda_vendedor"] == "FAZ. SANTO ANTONIO"

    def test_normaliza_fazenda_maiuscula(self):
        dados = {"fazenda_vendedor": "faz. juliana"}
        resultado = normalizar_dados(dados)
        assert resultado["fazenda_vendedor"] == "FAZ. JULIANA"

    def test_normaliza_timestamp_video(self):
        dados = {"timestamp_video": "26/03/2026 20:54:21"}
        resultado = normalizar_dados(dados)
        assert isinstance(resultado["timestamp_video"], datetime)
        assert resultado["timestamp_video"].year == 2026
        assert resultado["timestamp_video"].hour == 20


class TestValidarLote:
    def test_valida_lote_correto(self, dados_lote_valido, timestamp_fixture):
        resultado = validar_lote(dados_lote_valido, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.lote_numero == "0005"
        assert resultado.quantidade == 35
        assert resultado.raca == "Nelore"
        assert resultado.sexo == "macho"
        assert resultado.preco_lance == Decimal("3290")
        assert resultado.fazenda_vendedor == "FAZ. JULIANA"

    def test_valida_lote_sujo_apos_normalizacao(self, dados_lote_sujo, timestamp_fixture):
        resultado = validar_lote(dados_lote_sujo, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.sexo == "macho"
        assert resultado.local_estado == "SP"
        assert resultado.pelagem == "branco"
        assert resultado.fazenda_vendedor == "FAZ. SANTO ANTONIO"

    def test_rejeita_lote_invalido(self, dados_lote_invalido, timestamp_fixture):
        resultado = validar_lote(dados_lote_invalido, timestamp_frame=timestamp_fixture)
        assert resultado is None

    def test_rejeita_uf_inexistente(self, dados_lote_valido, timestamp_fixture):
        dados_lote_valido["local_estado"] = "ZZ"
        resultado = validar_lote(dados_lote_valido, timestamp_frame=timestamp_fixture)
        assert resultado is None

    def test_aceita_preco_zero(self, dados_lote_preco_zero, timestamp_fixture):
        resultado = validar_lote(dados_lote_preco_zero, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.preco_lance == Decimal("0")

    def test_aceita_lote_alfanumerico(self, dados_lote_alfanumerico, timestamp_fixture):
        resultado = validar_lote(dados_lote_alfanumerico, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.lote_numero == "001A"

    def test_lote_sem_idade_aceito(self, dados_lote_valido, timestamp_fixture):
        dados_lote_valido["idade_meses"] = None
        resultado = validar_lote(dados_lote_valido, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.idade_meses is None

    def test_lote_sem_pelagem_aceito(self, dados_lote_valido, timestamp_fixture):
        dados_lote_valido["pelagem"] = None
        resultado = validar_lote(dados_lote_valido, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.pelagem is None

    def test_lote_sem_fazenda_aceito(self, dados_lote_valido, timestamp_fixture):
        dados_lote_valido["fazenda_vendedor"] = None
        resultado = validar_lote(dados_lote_valido, timestamp_frame=timestamp_fixture)
        assert resultado is not None
        assert resultado.fazenda_vendedor is None
