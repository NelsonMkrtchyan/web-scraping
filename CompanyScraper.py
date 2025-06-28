import requests
from bs4 import BeautifulSoup
import re
import csv
import os
import time
import traceback
from urllib.parse import urljoin
import argparse

BASE_URL = "https://www.spyur.am"

# Default categories
CATEGORIES = {
    "real_estate": "https://www.spyur.am/am/yellow_pages/?type=bd&yp_cat1=&yp_cat2=l2.3.5&yp_cat3=&search=Search",
    "ԱՌԵՎՏՐԱՅԻՆ ԳՈՐԾԱՐՔՆԵՐ, ՅՈՒՐԱՀԱՏՈՒԿ ԱՌԵՎՏՐԱՅԻՆ ՀԱՐԹԱԿՆԵՐ, ՕԲՅԵԿՏՆԵՐ": "https://www.spyur.am/am/yellow_pages/?type=bd&yp_cat1=&yp_cat2=l2.3.6&yp_cat3=&search=Search",
    # "it": "https://www.spyur.am/am/yellow_pages/?type=bd&yp_cat1=&yp_cat2=l2.2.1&yp_cat3=&search=Search",
    # "finance": "https://www.spyur.am/am/yellow_pages/?type=bd&yp_cat1=&yp_cat2=l2.1.1&yp_cat3=&search=Search",
    # "tourism": "https://www.spyur.am/am/yellow_pages/?type=bd&yp_cat1=&yp_cat2=l2.5.1&yp_cat3=&search=Search"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

class CompanyScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def clean_director_name(self, director_text):
        """Clean up director name by removing titles, labels, and extra information"""
        if not director_text:
            return ""
            
        # Remove Armenian label "Ղեկավար" (Manager/Director)
        director_text = re.sub(r'\u0542\u0565\u056f\u0561\u057e\u0561\u0580\s*', '', director_text)
        
        # Remove common titles and positions
        director_text = re.sub(r'(?i)(director|manager|head|\u057f\u0576\u0585\u0580\u0565\u0576|ceo|president|owner|founder).*$', '', director_text)
        
        # Remove company type labels that might appear in director field (more comprehensive)
        company_type_patterns = [
            # "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ" (REAL ESTATE AGENCY)
            r'\u0531\u0546\u0547\u0531\u0550\u0541 \u0533\u0548\u0552\u0554\u053b \u0533\u0548\u0550\u053e\u0531\u053f\u0531\u053c\u0548\u0552\u0539\u0545\u0548\u0552\u0546\s*',
            # "սահմանափակ պատասխանատվությամբ ընկերություն" (LLC)
            r'\u057d\u0561\u0570\u0574\u0561\u0576\u0561\u0583\u0561\u056f \u057a\u0561\u057f\u0561\u057d\u056d\u0561\u0576\u0561\u057f\u057e\u0578\u0582\u0569\u0575\u0561\u0574\u0562 \u0568\u0576\u056f\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',
            # "ՍՊԸ" (LLC abbreviation)
            r'\u054d\u054a\u0538\s*',
            # "ՓԲԸ" (CJSC abbreviation)
            r'\u0553\u0532\u0538\s*',
            # Any other company type labels in Armenian
            r'\u0563\u0578\u0580\u056e\u0561\u056f\u0561\u056c\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',  # agency/representation
            r'\u0568\u0576\u056f\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',  # company
        ]
        
        for pattern in company_type_patterns:
            director_text = re.sub(pattern, '', director_text)
        
        # If the text is very long (likely contains mission statements or descriptions)
        # and contains Armenian names (typically have "յան", "յանց", or "ունի" endings)
        if len(director_text) > 40 and re.search(r'(\u0575\u0561\u0576|\u0578\u0582\u0576\u056b|\u0575\u0561\u0576\u0581)\b', director_text):
            # Try to extract just the name - typically Armenian names are 2-3 words and end with surname
            # Look for patterns like "Name Surname" or "Name MiddleName Surname" at the end of the text
            name_match = re.search(r'\b([\u0531-\u0587]+\s+[\u0531-\u0587]+\s+[\u0531-\u0587]+\s*[\u0531-\u0587]*|[\u0531-\u0587]+\s+[\u0531-\u0587]+)\s*$', director_text)
            if name_match:
                director_text = name_match.group(1).strip()
        
        # Remove common location words that might appear before the name
        location_words = [
            r'\u056f\u0565\u0576\u057f\u0580\u0578\u0576\s+',  # "կենտրոն" (center)
            r'\u0563\u056c\u056d\u0561\u0574\u0561\u057d\s+',  # "գլխամաս" (headquarters)
            r'\u0563\u0580\u0561\u057d\u0565\u0576\u0575\u0561\u056f\s+',  # "գրասենյակ" (office)
        ]
        
        for word in location_words:
            director_text = re.sub(word, '', director_text)
        
        # Remove trailing punctuation and spaces
        director_text = re.sub(r'[,\-:;]\s*$', '', director_text)
        
        # Remove extra whitespace and newlines
        director_text = re.sub(r'\s+', ' ', director_text)
        director_text = re.sub(r'\n+', ' ', director_text)
        
        return director_text.strip()
        
    def clean_address(self, address_text):
        """Clean up address text by removing phone numbers, working hours, and other non-address information"""
        # Remove phone numbers
        address_text = re.sub(r'\+374-\d{2}-\d{6}|\+374-\d{2}-\d{5}|\+374-\d{3}-\d{5}', '', address_text)
        
        # Remove working hours patterns
        days_pattern = r'\u0535\u0580\u056f\s+\u0535\u0580\u0584\s+\u0549\u0580\u0584\s+\u0540\u0576\u0563\s+\u0548\u0582\u0580\u0562\s+\u0547\u0562\u0569\s+\u053f\u056b\u0580\s+\d{1,2}:\d{2}-\d{1,2}:\d{2}'
        address_text = re.sub(days_pattern, '', address_text)
        
        # Remove shorter working hours patterns
        address_text = re.sub(r'\d{1,2}:\d{2}-\d{1,2}:\d{2}', '', address_text)
        
        # Remove labels like "\u0563\u0580\u0561\u057d\u0565\u0576\u0575\u0561\u056f`" (office)
        address_text = re.sub(r'\u0563\u0580\u0561\u057d\u0565\u0576\u0575\u0561\u056f`', '', address_text)
        
        # Remove "(\u0562\u057b\u057b.)" (mobile) labels
        address_text = re.sub(r'\(\u0562\u057b\u057b\.\)', '', address_text)
        
        # Remove "\u0533\u0578\u0580\u056e\u0578\u0582\u0576\u0565\u0578\u0582\u0569\u0575\u0561\u0576 \u0570\u0561\u057d\u0581\u0565" (Business Address) label
        address_text = re.sub(r'\u0533\u0578\u0580\u056e\u0578\u0582\u0576\u0565\u0578\u0582\u0569\u0575\u0561\u0576 \u0570\u0561\u057d\u0581\u0565', '', address_text)
        
        # Clean up extra whitespace, newlines, etc.
        address_text = re.sub(r'\s+', ' ', address_text)
        
        # Remove any remaining phone number patterns
        address_text = re.sub(r'\+\d+', '', address_text)
        
        # Trim whitespace
        address_text = address_text.strip()
        
        return address_text

    def get_company_links(self, list_url, max_pages=2):
        company_links = []
        for page in range(1, max_pages + 1):
            # Fix URL construction for pagination
            if '?' in list_url:
                url = f"{list_url}&page={page}"
            else:
                url = f"{list_url}?page={page}"
            print(f"Fetching list page: {url}")
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Try multiple selectors to find company links
            items = soup.select(".companies-list a.name") or soup.select(".company-name a") or soup.select(".company a")
            
            if not items:
                print(f"No company links found on page {page}. Trying alternative approach...")
                # Fallback to find all links that might be company pages
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href')
                    # Look for patterns that might indicate company pages
                    if '/am/companies/' in href or '/en/companies/' in href:
                        full_link = BASE_URL + href if not href.startswith('http') else href
                        if full_link not in company_links:
                            company_links.append(full_link)
            else:
                for item in items:
                    link = item.get("href")
                    if link:
                        full_link = BASE_URL + link if not link.startswith('http') else link
                        if full_link not in company_links:
                            company_links.append(full_link)
            
            print(f"Found {len(company_links)} company links so far")
            time.sleep(1)  # Be polite to the server
            
        return company_links
    
    def extract_company_info(self, company_url):
        """Extract general information about a company from its Spyur page"""
        try:
            # Skip Spyur Information System company
            if "spyur-information-system" in company_url or "spyur-information-center" in company_url:
                print(f"Skipping Spyur's own company page: {company_url}")
                return None
            
            print(f"Visiting: {company_url}")
            response = self.session.get(company_url)
            soup = BeautifulSoup(response.text, "html.parser")
            
            company_info = {
                "name": "",
                "director": "",
                "address": "",
                "phones": "",
                "website": "",
                "social_media": "",
                "source_url": company_url
            }
            
            # Extract company name
            name_elem = soup.select_one(".company-name") or soup.select_one("h1")
            if name_elem:
                company_info["name"] = name_elem.get_text().strip()
                print(f"Company name: {company_info['name']}")
            
            # Extract structured info from company-info-row elements
            info_rows = soup.select(".company-info-row")
            
            # Extract director/manager/head
            director_found = False
            for row in info_rows:
                label_elem = row.select_one('.info-label')
                value_elem = row.select_one('.info-value')
                if label_elem and value_elem:
                    label_text = label_elem.get_text().lower()
                    if 'director' in label_text or 'manager' in label_text or 'head' in label_text or '\u057f\u0576\u0585\u0580\u0565\u0576' in label_text:
                        # Get the raw text and clean it
                        raw_text = value_elem.get_text().strip()
                        # First check if it contains the problematic company type label
                        # "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ" (REAL ESTATE AGENCY)
                        agency_label = "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ"
                        if agency_label in raw_text:
                            # Extract only the name part after the label
                            parts = raw_text.split(agency_label)
                            if len(parts) > 1:
                                raw_text = parts[1].strip()
                        
                        # Then apply the general cleaning
                        director_name = self.clean_director_name(raw_text)
                        company_info["director"] = director_name
                        print(f"Director: {company_info['director']}")
                        director_found = True
                        break
            
            # If director not found in structured data, try regex approach
            if not director_found:
                # Look for patterns like "Name Surname, director" or "Name Surname - director"
                director_patterns = [
                    r'([A-Za-z\u0531-\u0587\s]+),?\s+(?:director|manager|head|տնօրեն)',
                    r'([A-Za-z\u0531-\u0587\s]+)\s+-\s+(?:director|manager|head|տնօրեն)'
                ]
                
                for pattern in director_patterns:
                    for elem in soup.find_all(['p', 'div', 'span']):
                        text = elem.get_text().strip()
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            # Get the raw text from the match
                            raw_text = match.group(1).strip()
                            # First check if it contains the problematic company type label
                            # "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ" (REAL ESTATE AGENCY)
                            agency_label = "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ"
                            if agency_label in raw_text:
                                # Extract only the name part after the label
                                parts = raw_text.split(agency_label)
                                if len(parts) > 1:
                                    raw_text = parts[1].strip()
                            
                            # Then apply the general cleaning
                            director_name = self.clean_director_name(raw_text)
                            company_info["director"] = director_name
                            print(f"Director: {company_info['director']}")
                            director_found = True
                            break
                    if director_found:
                        break
            
            # Extract address using multiple approaches
            address_found = False
            
            # Try to find address in the page content directly
            # Look for elements with specific text patterns that might contain addresses
            address_patterns = [
                'Երևան',  # Yerevan in Armenian
                'փողոց',  # Street in Armenian
                'պողոտա',  # Avenue in Armenian
                'հասցե'    # Address in Armenian
            ]
            
            # First try to find address in a structured way
            all_divs = soup.find_all('div')
            for div in all_divs:
                div_text = div.get_text().strip()
                # Check if this div contains address-like content
                if any(pattern in div_text for pattern in address_patterns) and len(div_text) < 200:
                    # Skip if it's just a heading or label
                    if len(div_text.split()) > 2 and not div_text.endswith(':'):
                        # Clean up the address
                        address = self.clean_address(div_text)
                        if address:
                            company_info["address"] = address
                            print(f"Address: {company_info['address']}")
                            address_found = True
                            break
            
            # If not found, try to find address in table-like structures
            if not address_found:
                # Look for table rows or definition lists that might contain address info
                rows = soup.select('tr, dt, dd')
                for row in rows:
                    elem_text = elem.get_text().strip()
                    # Check for common Armenian address patterns
                    if ('Երևան' in elem_text or 'ք․' in elem_text) and len(elem_text) < 200:
                        if any(word in elem_text for word in ['փող', 'պող', 'հասցե']):
                            # Clean up the address
                            address = self.clean_address(elem_text)
                            if address:
                                company_info["address"] = address
                                print(f"Address from text: {company_info['address']}")
                                address_found = True
                                break
            
            # Last resort: try to extract from the page URL
            if not address_found:
                # Extract the company name from the URL and use it as a placeholder
                url_parts = company_url.split('/')
                if len(url_parts) > 4:
                    company_name = url_parts[-2].replace('-', ' ').title()
                    company_info["address"] = f"Armenia" # Placeholder
                    print(f"Could not find specific address, using placeholder")
            
            # Extract phone numbers
            phones = []
            
            # First try to find phones in structured data
            for row in info_rows:
                label_elem = row.select_one('.info-label')
                value_elem = row.select_one('.info-value')
                if label_elem and value_elem:
                    label_text = label_elem.get_text().lower()
                    if 'phone' in label_text or 'tel' in label_text or 'հեռ' in label_text:
                        phone_text = value_elem.get_text().strip()
                        # Extract phone numbers with regex
                        phone_matches = re.findall(r'\+374-\d{2}-\d{6}|\+374-\d{2}-\d{5}|\+374-\d{3}-\d{5}', phone_text)
                        for match in phone_matches:
                            if match not in phones:
                                phones.append(match)
            
            # If no phones found in structured data, try to find them in the page content
            if not phones:
                # Look for phone number patterns in the page
                phone_patterns = [
                    r'\+374-\d{2}-\d{6}',
                    r'\+374-\d{2}-\d{5}',
                    r'\+374-\d{3}-\d{5}'
                ]
                
                for pattern in phone_patterns:
                    for elem in soup.find_all(['p', 'div', 'span']):
                        text = elem.get_text()
                        matches = re.findall(pattern, text)
                        for match in matches:
                            if match not in phones:
                                phones.append(match)
            
            # If still no phones, try a more aggressive approach
            if not phones:
                # Look for any text that might contain phone numbers
                for elem in soup.find_all(['p', 'div', 'span']):
                    text = elem.get_text()
                    # Look for patterns like "+374" followed by digits
                    matches = re.findall(r'\+374[-\s]?\d+[-\s]?\d+', text)
                    for match in matches:
                        clean_phone = re.sub(r'[^\d\+\-\(\)\s]', '', match).strip()
                        if clean_phone and clean_phone not in phones:
                            phones.append(clean_phone)
            
            # Limit to first 3 phones and join with commas
            company_info["phones"] = ", ".join(phones[:3]) if phones else ""
            if phones:
                print(f"Phones: {company_info['phones']}")
            
            # Extract website
            website_links = soup.select('a[href*="http"]')
            for link in website_links:
                href = link.get('href')
                if href and 'spyur.am' not in href and ('http://' in href or 'https://' in href):
                    # Skip social media links for website field
                    if not any(social in href.lower() for social in ['facebook', 'instagram', 'linkedin', 'twitter', 'youtube']):
                        company_info["website"] = href
                        print(f"Website: {company_info['website']}")
                        break
            
            # Extract social media links
            social_media_links = []
            for link in website_links:
                href = link.get('href')
                if href and any(social in href.lower() for social in ['facebook', 'instagram', 'linkedin', 'twitter']):
                    # Filter out Spyur's own social media links and any other Spyur links
                    if 'spyur' not in href.lower() and 'spyurinformationsystem' not in href.lower() and 'spyur-information-center' not in href.lower():
                        if href not in social_media_links:
                            social_media_links.append(href)
            
            company_info["social_media"] = ", ".join(social_media_links)
            if social_media_links:
                print(f"Social media: {company_info['social_media']}")
            
            return company_info
        except Exception as e:
            print(f"Error visiting {company_url}: {e}")
            return {
                "name": "",
                "director": "",
                "address": "",
                "phones": "",
                "website": "",
                "social_media": "",
                "source_url": company_url
            }

def save_to_csv(data, filepath):
    """Save scraped data to a CSV file
    
    Args:
        data (list): List of dictionaries containing company information
        filepath (str): Path to save the CSV file
    """
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        if data and len(data) > 0:
            fieldnames = data[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

def find_next_page_url(soup, current_url):
    """Find the URL for the next page in pagination
    
    Args:
        soup (BeautifulSoup): BeautifulSoup object of the current page
        current_url (str): Current page URL
        
    Returns:
        str or None: URL of the next page, or None if not found
    """
    try:
        # Check for the correct yellow_pages format
        yellow_pages_match = re.search(r'/yellow_pages(?:-([0-9]+))?/', current_url)
        # Also check for the old format just in case
        yellow_page_match = re.search(r'/yellow_page(?:-([0-9]+))?', current_url)
        page_match = re.search(r'[?&]page=([0-9]+)', current_url)
        
        # Determine current page number
        current_page = 1
        if yellow_pages_match:
            # If it's yellow_pages-2, yellow_pages-3, etc.
            if yellow_pages_match.group(1):
                current_page = int(yellow_pages_match.group(1))
            # If it's just yellow_pages (first page)
            else:
                current_page = 1
        elif yellow_page_match:
            # If it's yellow_page-2, yellow_page-3, etc.
            if yellow_page_match.group(1):
                current_page = int(yellow_page_match.group(1))
            # If it's just yellow_page (first page)
            else:
                current_page = 1
        elif page_match:
            current_page = int(page_match.group(1))
        
        print(f"Current page detected as: {current_page}")
        
        # Look for the paging element specific to Spyur.am
        paging_element = soup.find(class_='paging')
        if paging_element:
            print(f"Found paging element with {len(paging_element.find_all('a'))} links")
            
            # Find all page links that contain numeric text (likely page numbers)
            page_links = []
            for link in paging_element.find_all('a', href=True):
                # Check if the link text is numeric or contains a page number pattern
                link_text = link.text.strip()
                if link_text.isdigit() or re.search(r'^\d+$', link_text):
                    page_number = int(link_text)
                    if page_number == current_page + 1:  # This is the next page
                        next_url = link.get('href')
                        if next_url.startswith('/'):
                            return BASE_URL + next_url
                        return urljoin(BASE_URL, next_url)
                    page_links.append((page_number, link))
            
            # If we didn't find the exact next page number, look for the next highest page
            if page_links:
                # Sort by page number
                page_links.sort(key=lambda x: x[0])
                for page_number, link in page_links:
                    if page_number > current_page:
                        next_url = link.get('href')
                        if next_url.startswith('/'):
                            return BASE_URL + next_url
                        return urljoin(BASE_URL, next_url)
            
            # Try to find the active page and get the next one
            active_link = paging_element.find(class_='active')
            if active_link:
                # The active element might be inside an <a> or might be a separate element
                if active_link.name == 'a':
                    # Find all links in the paging element
                    all_links = paging_element.find_all('a', href=True)
                    try:
                        active_index = all_links.index(active_link)
                        if active_index < len(all_links) - 1:
                            next_link = all_links[active_index + 1]
                            next_url = next_link.get('href')
                            if next_url:
                                if next_url.startswith('/'):
                                    return BASE_URL + next_url
                                return urljoin(BASE_URL, next_url)
                    except ValueError:
                        pass  # Active link not found in the list
                else:
                    # Try to find the next sibling that is a link
                    next_link = active_link.find_next_sibling('a')
                    if next_link and next_link.get('href'):
                        next_url = next_link.get('href')
                        if next_url.startswith('/'):
                            return BASE_URL + next_url
                        return urljoin(BASE_URL, next_url)
        
        # If we couldn't find the next page using the paging element,
        # look for any links that might be for pagination
        # This includes links with text like "Next", "→", etc.
        next_indicators = ['Next', 'Հաջորդը', '→', '»', 'next', 'հաջորդ', 'հաջորդ էջ']
        for indicator in next_indicators:
            next_links = [a for a in soup.find_all('a', href=True) 
                         if indicator.lower() in a.text.strip().lower() or 
                         indicator.lower() in a.get('title', '').lower() or
                         indicator.lower() in a.get('class', [])]
            
            if next_links:
                # Filter out links that point to company pages
                valid_next_links = []
                for link in next_links:
                    href = link.get('href')
                    # Skip links to company pages
                    if '/companies/' not in href:
                        valid_next_links.append(link)
                
                if valid_next_links:
                    next_url = valid_next_links[0].get('href')
                    if next_url.startswith('/'):
                        return BASE_URL + next_url
                    return urljoin(BASE_URL, next_url)
        
        # If we still haven't found a next page link, try to construct it from the current URL
        # This is a fallback method that works for Spyur.am
        next_page = current_page + 1
        
        # Handle yellow_pages format (the correct format)
        if yellow_pages_match:
            # Extract the query parameters
            query_params = ''
            if '?' in current_url:
                query_params = current_url.split('?', 1)[1]
            
            # If we're on yellow_pages (first page), next should be yellow_pages-2
            if current_page == 1:
                # Make sure we're dealing with the first page format
                if '/yellow_pages/' in current_url and '/yellow_pages-' not in current_url:
                    # Get the base part of the URL (before query parameters)
                    base_url_parts = current_url.split('?')[0]
                    
                    # Ensure we have a trailing slash before adding the page number
                    if not base_url_parts.endswith('/'):
                        base_url_parts += '/'
                    
                    # Replace /yellow_pages/ with /yellow_pages-2/
                    base_url = re.sub(r'/yellow_pages/?', f'/yellow_pages-2/', base_url_parts)
                    
                    # Add query parameters if they exist
                    if query_params:
                        return f"{base_url}?{query_params}"
                    return base_url
            
            # If we're on yellow_pages-N, next should be yellow_pages-(N+1)
            elif current_page >= 2:
                # Get the base part of the URL (before query parameters)
                base_url_parts = current_url.split('?')[0]
                
                # Replace yellow_pages-N with yellow_pages-(N+1)
                base_url = re.sub(r'/yellow_pages-[0-9]+/?', f'/yellow_pages-{next_page}/', base_url_parts)
                
                # Add query parameters if they exist
                if query_params:
                    return f"{base_url}?{query_params}"
                return base_url
        
        # Handle old yellow_page format (for backward compatibility)
        elif yellow_page_match:
            # Extract the query parameters
            query_params = ''
            if '?' in current_url:
                query_params = current_url.split('?', 1)[1]
                base_url = current_url.split('?')[0]
            else:
                base_url = current_url
            
            # If we're on yellow_page (first page), next should be yellow_page-2
            if current_page == 1 and '/yellow_page' in current_url and '/yellow_page-' not in current_url:
                new_base_url = re.sub(r'/yellow_page', f'/yellow_page-2', base_url)
                if query_params:
                    return f"{new_base_url}?{query_params}"
                return new_base_url
            # If we're on yellow_page-N, next should be yellow_page-(N+1)
            elif current_page >= 2:
                new_base_url = re.sub(r'/yellow_page-[0-9]+', f'/yellow_page-{next_page}', base_url)
                if query_params:
                    return f"{new_base_url}?{query_params}"
                return new_base_url
        
        # Handle standard page parameter format
        elif page_match:
            return re.sub(r'page=[0-9]+', f'page={next_page}', current_url)
        elif '?' in current_url:
            return f"{current_url}&page={next_page}"
        else:
            # If no pagination format detected, try to find a better fallback
            
            # Check if we're on a category page that should use yellow_pages format
            if any(cat_url in current_url for cat_url in CATEGORIES.values()):
                # If we're already on a yellow_pages URL but no match was found earlier
                if '/yellow_pages' in current_url:
                    # Try to construct the next page URL
                    if '/yellow_pages/' in current_url and '/yellow_pages-' not in current_url:
                        # We're on the first page, next should be page 2
                        base_url = current_url.rstrip('/')
                        if '?' in base_url:
                            # Split URL into base part and query part
                            base_part = base_url.split('?')[0]
                            # Construct the next page URL with original query parameters
                            return f"{base_part.replace('/yellow_pages', '/yellow_pages-2')}?{query_params}"
                        else:
                            # No query parameters
                            return base_url.replace('/yellow_pages', '/yellow_pages-2')
                else:
                    # We're not on a yellow_pages URL yet, so add it
                    if current_url.endswith('/'):
                        return f"{current_url}yellow_pages/"
                    else:
                        return f"{current_url}/yellow_pages/"
            
            # Last resort: add a page parameter
            if current_url.endswith('/'):
                return f"{current_url}?page={next_page}"
            else:
                return f"{current_url}/?page={next_page}"
            
    except Exception as e:
        print(f"Error finding next page: {e}")
        traceback.print_exc()  # Print the full traceback for debugging
        return None

def get_company_links(list_url, max_pages=5, max_companies=1000):
    """Get company links from the list page using proper pagination
    
    Args:
        list_url (str): URL of the category list page
        max_pages (int): Maximum number of pages to scrape
        max_companies (int): Maximum number of companies to collect (for testing)
        
    Returns:
        list: List of company URLs
    """
    company_links = []
    current_url = list_url
    page_count = 0
    
    while page_count < max_pages and len(company_links) < max_companies:
        try:
            page_count += 1
            print(f"Fetching list page {page_count}: {current_url}")
            
            response = requests.get(current_url, headers=HEADERS)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract company links
            company_elements = soup.select(".company-title a") or soup.select(".result_item .title a") or soup.select("a[href*='/companies/']") 
            
            for element in company_elements:
                if len(company_links) >= max_companies:
                    print(f"Reached maximum number of companies ({max_companies})")
                    return company_links
                    
                href = element.get("href")
                if href and "/companies/" in href:
                    # Make sure we have the full URL
                    if href.startswith("/"):
                        href = "https://www.spyur.am" + href
                    if href not in company_links:
                        company_links.append(href)
            
            print(f"Found {len(company_links)} company links so far (limit: {max_companies})")
            
            # If we've reached our limit, stop
            if len(company_links) >= max_companies:
                print(f"Reached maximum number of companies ({max_companies})")
                break
                
            next_url = find_next_page_url(soup, current_url)
            
            if not next_url or next_url == current_url:
                print(f"No more pages found after page {page_count}")
                break
                
            current_url = next_url
            time.sleep(1)  # polite delay
            
        except Exception as e:
            print(f"Error fetching page {page_count}: {e}")
            break
    
    # If we have more companies than the limit, trim the list
    if len(company_links) > max_companies:
        company_links = company_links[:max_companies]
        
    return company_links

def extract_company_info(company_url):
    """Extract company information from a company page
    
    Args:
        company_url (str): URL of the company page
        
    Returns:
        dict: Dictionary containing company information
    """
    try:
        # Skip Spyur's own company page
        if "spyur-information-system" in company_url:
            print(f"Skipping Spyur's own company page: {company_url}")
            return None
        
        response = requests.get(company_url, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Initialize company data
        company_info = {
            'name': '',
            'director': '',
            'address': '',
            'phones': '',
            'website': '',
            'social_media': '',
            'category': '',
            "source_url": company_url
        }
        
        # Extract company name
        name_elem = soup.select_one(".company-title") or soup.select_one("h1")
        if name_elem:
            company_info["name"] = name_elem.text.strip()
        
        # Extract director name - try structured data first
        director_found = False
        structured_data = soup.select(".company-info .info-line")
        for item in structured_data:
            label = item.select_one(".info-label")
            value = item.select_one(".info-value")
            
            if label and value and "Ղեկավար" in label.text:
                director_text = value.text.strip()
                company_info["director"] = clean_director_name(director_text)
                director_found = True
                break
        
        # If director not found in structured data, try regex approach
        if not director_found:
            company_text = soup.get_text()
            director_match = re.search(r'Ղեկավար[:\s]+(.*?)(?:\n|$)', company_text)
            if director_match:
                director_text = director_match.group(1).strip()
                company_info["director"] = clean_director_name(director_text)
        
        # Extract Armenian address - look specifically for "Գործունեության հասցե" (Business Address)
        address_found = False
        
        # First, try to find the address_block element which contains the full address
        # This is the most reliable method based on our analysis
        address_block = soup.select_one(".address_block") or soup.select_one(".branch_block .address_block")
        if address_block:
            address_text = address_block.text.strip()
            if address_text and len(address_text) < 200:
                company_info["address"] = clean_address(address_text)
                address_found = True
        
        # If no address_block found, try the contacts_info container
        if not address_found:
            contacts_info = soup.select_one(".contacts_info")
            if contacts_info:
                # Look for text containing "Հայաստան" (Armenia) or "Երևան" (Yerevan)
                for elem in contacts_info.find_all(["div", "p", "span"]):
                    text = elem.text.strip()
                    if ("Հայաստան" in text or "Երևան" in text) and len(text) < 200:
                        company_info["address"] = clean_address(text)
                        address_found = True
                        break
        
        # Try multiple selectors for company info sections
        if not address_found:
            info_sections = [
                soup.select(".company-info .info-line"),  # Standard info lines
                soup.select(".company-details .info-line"),  # Alternative structure
                soup.select(".company-data tr"),  # Table-based structure
                soup.select(".contact-info .info-item")  # Contact info section
            ]
            
            # Check each info section for address
            for section in info_sections:
                if address_found:
                    break
                    
                for item in section:
                    # Different ways to identify label and value
                    label = item.select_one(".info-label") or item.select_one("th") or item.select_one("dt")
                    value = item.select_one(".info-value") or item.select_one("td") or item.select_one("dd")
                    
                    if not label or not value:
                        # Try to find label and value in the text content
                        item_text = item.text.strip()
                        parts = item_text.split(":", 1)
                        if len(parts) == 2:
                            label = parts[0].strip()
                            value = parts[1].strip()
                        else:
                            continue
                    else:
                        label = label.text.strip()
                        value = value.text.strip()
                    
                    # Check if this is an address field
                    address_keywords = ["հասցե", "Հասցե", "գտնվելու վայր", "Գտնվելու վայր", "գրասենյակ", "Գրասենյակ"]
                    if any(keyword in label for keyword in address_keywords):
                        address_text = value
                        company_info["address"] = clean_address(address_text)
                        address_found = True
                        break
        
        # If address not found in structured data, try regex approach with multiple patterns
        if not address_found:
            company_text = soup.get_text()
            address_patterns = [
                r'Գրասենյակ[:\s]+(.*?)(?:\n|$)',  # Office
                r'Գործունեության հասցե[:\s]+(.*?)(?:\n|$)',  # Business address
                r'Հասցե[:\s]+(.*?)(?:\n|$)',  # Address
                r'Գտնվելու վայրը[:\s]+(.*?)(?:\n|$)'  # Location
            ]
            
            for pattern in address_patterns:
                address_match = re.search(pattern, company_text)
                if address_match:
                    address_text = address_match.group(1).strip()
                    company_info["address"] = clean_address(address_text)
                    address_found = True
                    break
        
        # If still no address, look for specific address blocks
        if not address_found:
            # Look for elements that are likely to contain address information
            address_blocks = soup.select(".address-block, .contact-address, .company-address")
            for block in address_blocks:
                text = block.text.strip()
                if text and len(text) < 200:
                    company_info["address"] = clean_address(text)
                    address_found = True
                    break
        
        # If still no address, use a more targeted approach for elements with address-like content
        if not address_found:
            # Only consider elements that are likely to contain actual address information
            # and avoid navigation or general content areas
            for elem in soup.select(".contact-info p, .company-info p, .address p, .location p, div.branch_block div"):
                text = elem.text.strip()
                if ("Հայաստան" in text or "Երևան" in text) and len(text) < 200:
                    # Avoid elements that are clearly not addresses
                    if not any(x in text.lower() for x in ["ավելացնել", "գործունեության տեսակներ", "ապրանք-ծառայություններ"]):
                        company_info["address"] = clean_address(text)
                        address_found = True
                        break
        
        # If we still don't have an address, default to "Հայաստան, Երևան" (Armenia, Yerevan)
        if not address_found or not company_info["address"]:
            company_info["address"] = "Հայաստան, Երևան"
        
        # Extract phone numbers
        phones = []
        
        # Try structured phone elements first
        phone_elements = soup.select(".company-phones .phone-item")
        for phone in phone_elements:
            phone_text = phone.text.strip()
            # Clean and format phone number
            phone_text = re.sub(r'[^\d+]', '', phone_text)
            if phone_text and len(phone_text) >= 8:  # Minimum valid phone length
                phones.append(phone_text)
        
        # If no phones found, try alternative selectors
        if not phones:
            # Try info-lines with phone labels
            for item in structured_data:
                label = item.select_one(".info-label")
                value = item.select_one(".info-value")
                
                if label and value and ("հեռ" in label.text.lower() or "տել" in label.text.lower() or "phone" in label.text.lower()):
                    phone_text = value.text.strip()
                    # Extract all phone numbers using regex
                    phone_matches = re.findall(r'[+]?[\d\s\(\)\-]{7,20}', phone_text)
                    for match in phone_matches:
                        clean_phone = re.sub(r'[^\d+]', '', match)
                        if clean_phone and len(clean_phone) >= 8:
                            phones.append(clean_phone)
        
        # If still no phones, try to find any phone-like patterns in the page
        if not phones:
            # Look for phone patterns in the entire page
            all_text = soup.get_text()
            phone_matches = re.findall(r'[+]?[\d\s\(\)\-]{7,20}', all_text)
            for match in phone_matches:
                clean_phone = re.sub(r'[^\d+]', '', match)
                if clean_phone and len(clean_phone) >= 8 and len(clean_phone) <= 15:
                    phones.append(clean_phone)
        
        # Limit to first 3 phones and join with commas
        if phones:
            company_info["phones"] = ", ".join(phones[:3])
        
        # Extract website
        website_elem = soup.select_one("a[href*='http']:not([href*='facebook']):not([href*='instagram']):not([href*='linkedin']):not([href*='spyur.am'])")
        if website_elem and website_elem.get("href"):
            website_url = website_elem.get("href").strip()
            if website_url and not website_url.startswith("https://www.spyur.am"):
                company_info["website"] = website_url
        
        # Extract social media links
        social_media_links = []
        social_media_elements = soup.select("a[href*='facebook'], a[href*='instagram'], a[href*='linkedin'], a[href*='twitter'], a[href*='youtube']")
        
        for social in social_media_elements:
            social_url = social.get("href").strip()
            # Skip Spyur's own social media
            if "spyur" not in social_url.lower() and social_url not in social_media_links:
                social_media_links.append(social_url)
        
        if social_media_links:
            company_info["social_media"] = ", ".join(social_media_links)
        
        return company_info
    except Exception as e:
        print(f"Error visiting {company_url}: {e}")
        return {
            "name": "",
            "director": "",
            "address": "",
            "phones": "",
            "website": "",
            "social_media": "",
            "source_url": company_url
        }

def clean_director_name(director_text):
    """Clean up director name by removing titles, labels, and extra information"""
    if not director_text:
        return ""
        
    # Remove Armenian label "Ղեկավար" (Manager/Director)
    director_text = re.sub(r'\u0542\u0565\u056f\u0561\u057e\u0561\u0580\s*', '', director_text)
    
    # Remove common titles and positions (both English and Armenian)
    titles_pattern = r'(?i)(director|manager|head|\u057f\u0576\u0585\u0580\u0565\u0576|ceo|president|owner|founder|\u0576\u0561\u056d\u0561\u0563\u0561\u0570|\u0570\u056b\u0574\u0576\u0561\u0564\u056b\u0580|\u057f\u0576\u0585\u0580\u0565\u0576|\u0572\u0565\u056f\u0561\u057e\u0561\u0580|\u0574\u0565\u0576\u0565\u057b\u0565\u0580|\u0562\u0561\u056a\u0576\u056b \u0572\u0565\u056f\u0561\u057e\u0561\u0580).*$'
    director_text = re.sub(titles_pattern, '', director_text)
    
    # Remove position descriptions that appear after a comma
    director_text = re.sub(r',.*$', '', director_text)
    
    # Remove company type labels that might appear in director field (more comprehensive)
    company_type_patterns = [
        # "ԱՆՇԱՐԺ ԳՈՒՅՔԻ ԳՈՐԾԱԿԱԼՈՒԹՅՈՒՆ" (REAL ESTATE AGENCY)
        r'\u0531\u0546\u0547\u0531\u0550\u0541 \u0533\u0548\u0552\u0554\u053b \u0533\u0548\u0550\u053e\u0531\u053f\u0531\u053c\u0548\u0552\u0539\u0545\u0548\u0552\u0546\s*',
        # "սահմանափակ պատասխանատվությամբ ընկերություն" (LLC)
        r'\u057d\u0561\u0570\u0574\u0561\u0576\u0561\u0583\u0561\u056f \u057a\u0561\u057f\u0561\u057d\u056d\u0561\u0576\u0561\u057f\u057e\u0578\u0582\u0569\u0575\u0561\u0574\u0562 \u0568\u0576\u056f\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',
        # "ՍՊԸ" (LLC abbreviation)
        r'\u054d\u054a\u0538\s*',
        # "ՓԲԸ" (CJSC abbreviation)
        r'\u0553\u0532\u0538\s*',
        # Any other company type labels in Armenian
        r'\u0563\u0578\u0580\u056e\u0561\u056f\u0561\u056c\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',  # agency/representation
        r'\u0568\u0576\u056f\u0565\u0580\u0578\u0582\u0569\u0575\u0578\u0582\u0576\s*',  # company
    ]
    
    for pattern in company_type_patterns:
        director_text = re.sub(pattern, '', director_text)
    
    # If the text is very long (likely contains mission statements or descriptions)
    # and contains Armenian names (typically have "յան", "յանց", or "ունի" endings)
    if len(director_text) > 40 and re.search(r'(\u0575\u0561\u0576|\u0578\u0582\u0576\u056b|\u0575\u0561\u0576\u0581)\b', director_text):
        # Try to extract just the name - typically Armenian names are 2-3 words and end with surname
        # Look for patterns like "Name Surname" or "Name MiddleName Surname" at the end of the text
        name_match = re.search(r'\b([\u0531-\u0587]+\s+[\u0531-\u0587]+\s+[\u0531-\u0587]+\s*[\u0531-\u0587]*|[\u0531-\u0587]+\s+[\u0531-\u0587]+)\s*$', director_text)
        if name_match:
            director_text = name_match.group(1).strip()
    
    # Remove common location words that might appear before the name
    location_words = [
        r'\u056f\u0565\u0576\u057f\u0580\u0578\u0576\s+',  # "կենտրոն" (center)
        r'\u0563\u056c\u056d\u0561\u0574\u0561\u057d\s+',  # "գլխամաս" (headquarters)
        r'\u0563\u0580\u0561\u057d\u0565\u0576\u0575\u0561\u056f\s+',  # "գրասենյակ" (office)
    ]
    
    for word in location_words:
        director_text = re.sub(word, '', director_text)
    
    # Remove trailing punctuation and spaces
    director_text = re.sub(r'[,\-:;]\s*$', '', director_text)
    
    # Remove extra whitespace and newlines
    director_text = re.sub(r'\s+', ' ', director_text)
    director_text = re.sub(r'\n+', ' ', director_text)
    
    return director_text.strip()

def clean_address(address_text):
    """Clean up address text by removing phone numbers, working hours, and other non-address information"""
    if not address_text:
        return ""
    
    # Remove phone numbers
    address_text = re.sub(r'[\+\d\(\)\-\s]{7,}', '', address_text)
    
    # Remove working hours (handle both colon and period separators)
    address_text = re.sub(r'\b\d{1,2}[:\.]\d{2}\s*-\s*\d{1,2}[:\.]\d{2}\b', '', address_text)
    
    # Remove email addresses
    address_text = re.sub(r'\S+@\S+\.\S+', '', address_text)
    
    # Remove URLs
    address_text = re.sub(r'https?://\S+', '', address_text)
    address_text = re.sub(r'www\.\S+', '', address_text)
    
    # Remove common non-address text
    non_address_patterns = [
        r'աշխատանքային ժամեր.*$',  # Working hours
        r'հեռ\..*$',  # Phone abbreviation
        r'հեռախոս.*$',  # Phone
        r'տել\..*$',  # Tel abbreviation
        r'բջջ\..*$',  # Mobile abbreviation
        r'էլ\..*$',  # Email abbreviation
        r'կայք.*$',  # Website
    ]
    
    for pattern in non_address_patterns:
        address_text = re.sub(pattern, '', address_text, flags=re.IGNORECASE)
    
    # Fix building number formats
    # Handle building numbers with slashes like "8/3 շենք"
    address_text = re.sub(r'(\d+)/(\d+)\s*շենք', r'\1/\2 շենք', address_text)
    # Replace /շենք with just շենք
    address_text = re.sub(r'/շենք', ' շենք', address_text)
    # Ensure there's a space before շենք if there's a number
    address_text = re.sub(r'(\d+)շենք', r'\1 շենք', address_text)
    # Fix missing building numbers (replace just շենք with appropriate format)
    address_text = re.sub(r'(?<![\d\s])շենք', ' շենք', address_text)
    # Fix floor information format
    address_text = re.sub(r'(\d+)րդ հարկ', r'\1-րդ հարկ', address_text)
    address_text = re.sub(r'(\d+)ին հարկ', r'\1-ին հարկ', address_text)
    # Don't add double hyphens
    address_text = re.sub(r'--ին հարկ', '-ին հարկ', address_text)
    address_text = re.sub(r'--րդ հարկ', '-րդ հարկ', address_text)
    
    # Clean up newlines and tabs first
    address_text = re.sub(r'[\n\t\r]+', ' ', address_text)
    
    # Add space after city name if missing
    address_text = re.sub(r'(Երևան)([^\s,])', r'\1 \2', address_text)
    
    # Clean up extra spaces, commas, etc.
    address_text = re.sub(r'\s+', ' ', address_text)
    address_text = re.sub(r'\s*,\s*', ', ', address_text)
    address_text = re.sub(r'^\s*,\s*', '', address_text)
    address_text = re.sub(r'\s*,\s*$', '', address_text)
    
    # Skip non-address content that appears in some pages
    if "Ապրանք-ծառայություններ` Հայաստանում" in address_text:
        return "Հայաստան, Երևան"  # Default to Armenia, Yerevan if specific address not found
    
    # If address doesn't contain Armenia or Yerevan, add it
    if "Հայաստան" not in address_text and "Երևան" not in address_text:
        address_text = "Հայաստան, Երևան, " + address_text
    
    # Remove trailing punctuation and spaces
    address_text = re.sub(r'[,\-:;]\s*$', '', address_text)
    
    # Remove duplicate commas
    address_text = re.sub(r',\s*,', ',', address_text)
    
    return address_text.strip()

def list_categories():
    """List available categories for scraping
    
    Returns:
        dict: Dictionary of category names and URLs
    """
    print("Available categories for scraping:")
    for i, (name, url) in enumerate(CATEGORIES.items(), 1):
        print(f"{i}. {name.replace('_', ' ').title()}")
    return CATEGORIES

def scrape_all_categories(max_pages=5, max_companies=1000, output_path=None):
    """Scrape all categories defined in the CATEGORIES dictionary
    
    Args:
        max_pages (int, optional): Maximum number of pages to scrape per category. Defaults to 5.
        max_companies (int, optional): Maximum number of companies to scrape per category. Defaults to 1000.
        output_path (str, optional): Path to save the CSV file. Defaults to user's Documents folder.
    """
    all_companies_data = []
    
    for category_name, category_url in CATEGORIES.items():
        print(f"\n{'=' * 80}")
        print(f"📂 Processing category: {category_name.upper()}")
        print(f"{'=' * 80}")
        
        # Call main function for each category
        companies_data = main(category=category_name, max_pages=max_pages, max_companies=max_companies, output_path=None, return_data=True)
        
        if companies_data:
            all_companies_data.extend(companies_data)
            print(f"✅ Added {len(companies_data)} companies from category '{category_name}'")
        else:
            print(f"❌ No companies found in category '{category_name}'")
    
    # Save all data to CSV
    if all_companies_data:
        # Determine output path
        if not output_path:
            output_path = os.path.expanduser("~/Documents/spyur_all_categories.csv")
        
        save_to_csv(all_companies_data, output_path)
        print(f"\n✅ Scraped {len(all_companies_data)} companies from all categories and saved to {output_path}")
        print(f"CSV file saved at: {output_path}")
    else:
        print("\n❌ No company data was scraped from any category.")

def main(category=None, max_pages=10, max_companies=1000, output_path=None, return_data=False):
    """Main function to scrape company information
    
    Args:
        category (str, optional): Category to scrape. Defaults to real_estate.
        max_pages (int, optional): Maximum number of pages to scrape. Defaults to 10.
        max_companies (int, optional): Maximum number of companies to scrape. Defaults to 1000.
        output_path (str, optional): Path to save the CSV file. Defaults to user's Documents folder.
        return_data (bool, optional): Whether to return the scraped data. Defaults to False.
        
    Returns:
        list: List of company data dictionaries if return_data is True, otherwise None
    """
    try:
        # Get category URL
        if category and category in CATEGORIES:
            list_url = CATEGORIES[category]
            category_name = category
        elif category and category.startswith('http'):
            # If a full URL is provided
            list_url = category
            category_name = "custom_url"
        else:
            # Default to real estate
            list_url = CATEGORIES['real_estate']
            category_name = "real_estate"
        
        # Get company links
        print(f"🔍 Fetching company links from category '{category_name}', scanning up to {max_pages} pages and {max_companies} companies...")
        company_links = get_company_links(list_url, max_pages=max_pages, max_companies=max_companies)
        print(f"📋 Found {len(company_links)} company links in category '{category_name}'")
        
        
        if not company_links:
            print(f"❌ No company links found in category '{category_name}'. Please check the URL or try a different category.")
            return [] if return_data else None
        
        # Extract company info for each link
        companies_data = []
        for i, link in enumerate(company_links, 1):
            try:
                print(f"\nProcessing company {i}/{len(company_links)}")
                print(f"Visiting: {link}")
                
                # Skip Spyur's own company page
                if "spyur-information-system" in link:
                    print(f"Skipping Spyur's own company page: {link}")
                    continue
                    
                company_info = extract_company_info(link)
                
                # Add category information to the company data
                company_info['category'] = category_name
                
                # Print extracted info
                print(f"Company name: {company_info['name']}")
                if company_info['director']:
                    print(f"Director: {company_info['director']}")
                if company_info['address']:
                    print(f"Address: {company_info['address']}")
                if company_info['phones']:
                    print(f"Phones: {company_info['phones']}")
                if company_info['website']:
                    print(f"Website: {company_info['website']}")
                if company_info['social_media']:
                    print(f"Social media: {company_info['social_media']}")
                print(f"Category: {company_info['category']}")
                
                
                companies_data.append(company_info)
                time.sleep(1)  # Be polite with the server
            except Exception as e:
                print(f"Error processing company {link}: {str(e)}")
                continue
        
        # Save to CSV if output_path is provided
        if companies_data:
            if output_path:
                save_to_csv(companies_data, output_path)
                print(f"\n✅ Scraped {len(companies_data)} companies from category '{category_name}' and saved to {output_path}")
                print(f"CSV file saved at: {output_path}")
                
                # Print sample of the data
                print("\nSample of scraped data:\n")
                for i, company in enumerate(companies_data[:3], 1):
                    print(f"Company {i}: {company['name']}")
                    print(f"Director: {company['director']}")
                    print(f"Address: {company['address']}")
                    print(f"Phones: {company['phones']}")
                    print(f"Website: {company['website']}")
                    print(f"Social Media: {company['social_media'][:100]}{'...' if len(company['social_media']) > 100 else ''}\n")
            else:
                print(f"\n✅ Scraped {len(companies_data)} companies from category '{category_name}'")
        else:
            print(f"\n❌ No company data was scraped from category '{category_name}'")
            
        # Return the data if requested
        if return_data:
            return companies_data
        return None
    except Exception as e:
        print(f"An error occurred during scraping: {str(e)}")
        traceback.print_exc()
        if return_data:
            return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape company information from Spyur.am")
    parser.add_argument("-c", "--category", choices=list(CATEGORIES.keys()), help="Category to scrape (default: real_estate)")
    parser.add_argument("-p", "--pages", type=int, default=5, help="Maximum number of pages to scrape (default: 5)")
    parser.add_argument("-m", "--max-companies", type=int, default=1000, help="Maximum number of companies to scrape per category (default: 1000)")
    parser.add_argument("-o", "--output", type=str, help="Path to save the CSV file (default: user's Documents folder)")
    parser.add_argument("-l", "--list", action="store_true", help="List available categories and exit")
    parser.add_argument("-u", "--url", type=str, help="Custom URL to scrape (overrides category)")
    parser.add_argument("-a", "--all", action="store_true", help="Scrape all categories")
    args = parser.parse_args()
    
    if args.list:
        list_categories()
    elif args.all:
        print(f"\n📊 Scraping all categories with max {args.pages} pages and max {args.max_companies} companies per category...")
        scrape_all_categories(max_pages=args.pages, output_path=args.output, max_companies=args.max_companies)
    else:
        # Use URL if provided, otherwise use category
        category_arg = args.url if args.url else args.category
        print(f"\n📊 Scraping with max {args.pages} pages and max {args.max_companies} companies...")
        main(category=category_arg, max_pages=args.pages, output_path=args.output, max_companies=args.max_companies)
