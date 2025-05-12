import * as pdfmake from 'pdfmake/build/pdfmake';
import * as pdffonts from 'pdfmake/build/vfs_fonts';
(pdfmake as any).vfs = pdffonts.vfs;
import { TDocumentDefinitions } from 'pdfmake/interfaces';
import * as fs from 'fs';

type SmellTable = Record<string, Record<string, string[]>>;

export class pdfGenerator {

    private data: SmellTable;

    constructor(data: SmellTable) {
        this.data = data;
    }

    public async generate(outputPath: string) {
        const isEntireProject = Object.keys(this.data).length > 1;
        
        // Define the document definition
        const docDefinition: TDocumentDefinitions = {
            info: {
                title: 'Code Smell Report',
            },
            content: this.createData(),
            header: (currentPage: number, pageCount: number) => {
                return {
                    columns: [
                        {
                            text: 'Code Smell Report',
                            alignment: 'left',
                            margin: [40, 10, 0, 0] // left, top, right, bottom
                        },
                        {
                            text: (isEntireProject ? 'Entire Project' : 'Single File'),
                            alignment: 'right',
                            margin: [0, 10, 40, 0] // left, top, right, bottom
                        }
                    ],
                    margin: [40, 20] // left, top
                };
            },
            footer: (currentPage: number, pageCount: number) => {
                return {
                    columns: [
                        {
                            text: `Page ${currentPage} of ${pageCount}`,
                            alignment: 'center',
                            margin: [0, 0, 0, 10] // bottom margin
                        }
                    ]
                };
            },
            styles: {
                tableTopHeader: {
                    bold: true,
                    fillColor: '#102E4A',
                    color: 'white',
                    margin: [10, 10, 10, 10], // left, top, right, bottom
                },
                tableHeader: {
                    bold: true,
                    fillColor: '#AAE0FF',
                    color: 'black',
                    margin: [0, 5, 0, 5], // left, top, right, bottom
                    alignment: 'center',
                },
                tableBodyEven: {
                    fillColor: 'white',
                    color: 'black',
                    margin: [10, 5, 10, 5], // left, top, right, bottom
                },
                tableBodyOdd: {
                    fillColor: '#F5FCFF',
                    color: 'black',
                    margin: [10, 5, 10, 5], // left, top, right, bottom
                }
            },
            pageSize: 'A4',
            pageOrientation: 'portrait',
            pageMargins: [40, 60, 40, 60], // left, top, right, bottom
        };

        // Create the PDF and write it to a file
        return new Promise<void>((resolve, reject) => {
            try {
            pdfmake.createPdf(docDefinition).getBuffer((buffer) => {
                try {
                fs.writeFileSync(outputPath, buffer);
                console.log(`PDF generated at ${outputPath}`);
                resolve();
                } catch (err) {
                reject(err);
                }
            });
            } catch (err) {
            reject(err);
            }
        });
    }

    private createData() : any[] {
        const fileNames = Object.keys(this.data);

        const content : any[] = [];

        fileNames.forEach((fileName, index) => {
            const tableFileName = [
                { 
                    text: `File Name: ${fileName}`, 
                    colSpan: 2, 
                    alignment: 'left',
                    style: 'tableTopHeader',
                 }, ''
            ];
            const tableHeader = [
                { text: 'Scope', style: 'tableHeader' },
                { text: 'Smells', style: 'tableHeader' }
            ];
            const tableBody = [];
            const tableBodySmells = this.data[fileName];
            let rowCount = 0;
            for (const scope in tableBodySmells) {
                rowCount++;
                const style = (rowCount % 2 === 0) ? 'tableBodyEven' : 'tableBodyOdd';
                const smells = tableBodySmells[scope];
                const cell = {
                    text: scope,
                    style: style
                };
                const cell2 = {
                    text: smells.join(', ') || 'No Smells Found',
                    style: style
                };
                tableBody.push([cell, cell2]);
            }

            const tableContent = {
                layout: "headerLineOnly",
                table: {
                    headerRows: 2,
                    widths: ['*', '*'],
                    body: [
                        tableFileName,
                        tableHeader,
                        ...tableBody
                    ]
                }
            }

            if (index < fileNames.length - 1) {
                content.push(tableContent, { text: '',  pageBreak: 'after' });
            } else {
                content.push(tableContent);
            }
        })
        

        return content;
    }
}