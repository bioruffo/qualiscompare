#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 28 14:20:44 2019

@author: roberto
"""

from PyPDF2 import PdfFileReader
from collections import namedtuple, OrderedDict
import requests
import re
import bs4
from plotly import offline as py
import plotly.graph_objs as go
from plotly import tools


Data = namedtuple('Data', ['ISSN', 'TITULO', 'ESTRATO'])


def get_data(text):
    '''
    Extract Qualis data from a Qualis webpage on Sucupira Platform.
    
    :param str text: the webpage's text.
    :return: a list of Data namedtuples.
    '''
    soup = bs4.BeautifulSoup(text, features="html5lib")
    try:
        results = soup.find_all('div', 'resultados')[0].table.tbody
    except IndexError:
        print("Found no records.")
        return []
    each = [item for item in results.children if 'td' in str(item)]
    all_data = []
    for record in each:
        issn, titulo, area, estrato = [item.get_text().strip() for item in record.find_all('td')]
        all_data.append(Data(issn, titulo, estrato))
    print('Found {} records, "{}" to "{}"'.format(len(all_data), all_data[0][1], all_data[-1][1]))
    return all_data


def save_data(filename, all_data, compare = False):
    '''
    Save data to a file.
    
    :param str filename: output file name.
    :param list all_data: list of Data namedtuples to be saved on file.
    :param compare: if provided, must be a dictionary for cross-referencing Data.ISSN and qualis score.
    '''
    
    print("Saving to:", filename)
    header = ["ISSN", "TITULO", "ESTRATO"]
    if compare is not False:
        header.append('NOVA_CLASSIF')
    with open(filename, "w") as f:
        f.write('\t'.join(header)+'\n')
        for data in all_data:
            if compare is not False:
                data = [x for x in data] + [compare.get(data.ISSN, 'N/A')]
            f.write('\t'.join(data)+'\n')


def read_pdf(filename):
    '''
    Read Qualis data from the provided PDF.
    :param str filename: Location of the file on disk.
    :return: a list of Data namedtuples.
    '''
    
    journals_new = []
    pdf = PdfFileReader(open(filename, 'rb'))
    
    for pageno in range(pdf.numPages):
        page = pdf.getPage(pageno)
        text = page.extractText()
        if text.strip() != '':
            text = text.split('\n')
            if pageno == 0 and text[0] == 'ISSN':
                text = text[3:]
            if text[-1] == '':
                text = text[:-1]
            assert len(text) % 3 == 0
            for issn, titulo, estrato in [(text[i], text[i+1], text[i+2]) \
                                          for i in range(0, len(text), 3)]:
                try:
                    assert estrato in ['A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3', 'B4', 'C', 'NP']
                except AssertionError:
                    print("ERRO - Estrato não encontrado: ", issn, titulo, estrato)
                    continue
                journals_new.append(Data(issn, titulo, estrato))
    print("Imported {} journals.".format(len(journals_new)))
    return journals_new


def fetch_www(qualislevs):
    '''
    Scrape Qualis data (for "Medicina II") on the Sucupira Platform.
    :param list qualislevs: list of Qualis classifications e.g. ['A1', 'A2'...]
    '''
    url = 'https://sucupira.capes.gov.br/sucupira/public/consultas/coleta/veiculoPublicacaoQualis/listaConsultaGeralPeriodicos.xhtml'
    r = requests.get(url)
    cookies = r.cookies
    viewstate = re.findall('name=\"javax\.faces\.ViewState\" id=\"javax\.faces\.ViewState\" value=\"([\S]*?)\" autocomplete=', r.text)[0]
    
    first = '?form=form&form%3Aevento=156&form%3AcheckArea=on&form%3Aarea=16&form%3Aissn%3Aissn=&form%3Aj_idt49=&form%3AcheckEstrato=on&form%3Aestrato={}&form%3Aconsultar=Consultar&javax.faces.ViewState={}'
    nexts = '?form=form&form%3Aevento=156&form%3AcheckArea=on&form%3Aarea=16&form%3Aissn%3Aissn=&form%3Aj_idt49=&form%3AcheckEstrato=on&form%3Aestrato={}&form%3Aj_idt60%3Aj_idt67={}&javax.faces.ViewState={}&javax.faces.source=form%3Aj_idt60%3AbotaoProxPagina&javax.faces.partial.event=click&javax.faces.partial.execute=form%3Aj_idt60%3AbotaoProxPagina%20%40component&javax.faces.partial.render=%40component&javax.faces.behavior.event=action&org.richfaces.ajax.component=form%3Aj_idt60%3AbotaoProxPagina&AJAX%3AEVENTS_COUNT=1&javax.faces.partial.ajax=true'
    
    select = dict(zip(qualislevs, range(21, 21+len(qualislevs))))
    
    journals_old = []
    
    for level in qualislevs:
        print("Loading data for Qualis", level)
        print("Loading first page")
        firstpage = requests.get(url + first.format(select[level], viewstate), cookies=cookies)
        journals_old.extend(get_data(firstpage.text))
        regs = re.findall('<li>1 a ([\d]*?) de ([\d]*?) registro\(s\)\\n', firstpage.text)[0]
        regs_per_page, totregs = [int(x) for x in regs]
        npages = int(totregs/regs_per_page)
        if npages * regs_per_page < totregs:
            npages += 1
        
        for pageno in range(1, npages+1):
            print("Loading page {}".format(pageno+1))
            nextpage = requests.get(url + nexts.format(select[level], pageno, viewstate), cookies=cookies)
            journals_old.extend(get_data(nextpage.text))
    noreps = []
    for item in journals_old:
        if item not in noreps:
            noreps.append(item)
    journals_old = noreps    
    print("Fetched {} records.".format(len(journals_old)))
    return journals_old


if __name__ == '__main__':
    print("Importing data from qualis PDF...")
    pdfname = './2019_novo_qualis.pdf'
    journals_new = read_pdf(pdfname)
    save_data("novo_qualis.tsv", journals_new)

    print("Fetching current Qualis data...")
    oldlevs = ['A1', 'A2', 'B1', 'B2', 'B3', 'B4', 'B5', 'C']
    journals_old = fetch_www(oldlevs)
    save_data('medicina_II.tsv', journals_old)
    
    new_dict = OrderedDict((x.ISSN, x.ESTRATO) for x in journals_new)
    
    print("Adding new classification to old data...")
    save_data('medicina_II_plusNew.tsv', journals_old, new_dict)
    
    print('Plotting data...')
    newlevs = sorted(set([item.ESTRATO for item in journals_new]))
    fig = tools.make_subplots(rows=5, cols = 2, subplot_titles=['Novo_'+lev for lev in newlevs])
    all_counts = dict()
    for j, new in enumerate(newlevs):
        all_counts[new] = [0 for i in range(len(oldlevs))]
        for i, old in enumerate(oldlevs):
            counts = sum([item.ESTRATO == old and new_dict.get(item.ISSN, False) == new \
                          for item in journals_old])
            all_counts[new][i] = counts
        fig.add_trace(go.Bar(x=oldlevs, y=all_counts[new]), int(j/2)+1, int(j%2)+1)
    fig['layout'].update(hovermode='closest', height=1800,
                     showlegend=False)
    py.plot(fig, filename="qualis_comparison2.html")
    
    
    
    
            
    
    
    
    

    
        
        
        
        
        

    